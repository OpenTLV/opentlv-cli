#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Prepare an immutable release request and reject incomplete release evidence."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MATRIX = {(system, shared) for system in ("Linux", "Windows") for shared in ("ON", "OFF")}
BUILD_CASES = {"git-fallback", "local-override", "installed-package", "override-before-package", "workspace"}
REJECTION_CASES = {"fallback-package-trap", "missing-cxx", "legacy-cxx", "missing-core",
                   "cxx-disabled", "invalid-source"}
TESTS = {"core_c_smoke", "core_cxx_smoke", "cli_version", "cli_version_contract", "cli_release_gate",
         "Integration_cli_migration", "Integration_cli", "Integration_cli_cpp_examples",
         "Integration_cli_baseline_runner", "Integration_cli_baseline", "query-cli-conformance"}
QUERY_EXCLUSIONS = [{"id": name, "reason": "requires external fixture name resolver"}
                    for name in ("f3-function-name-positive", "f3-function-name-negative")]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, encoding="utf-8").strip()


def validate_request(request):
    for key in ("cli_sha", "core_sha", "json_sha", "workflow_sha"):
        require(isinstance(request.get(key), str) and re.fullmatch(r"[0-9a-f]{40}", request[key]),
                f"Invalid full SHA: {key}")
    tag = request.get("tag", "")
    require(isinstance(tag, str) and re.fullmatch(
        r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?", tag),
        "Expected vMAJOR.MINOR.PATCH with optional SemVer prerelease")
    if "-" in tag:
        for part in tag.split("-", 1)[1].split("."):
            require(not (part.isdigit() and len(part) > 1 and part.startswith("0")),
                    "Leading zero in numeric prerelease")
    require(request.get("version") == tag[1:], "Tag/version mismatch")
    for key in ("run_id", "run_attempt"):
        require(isinstance(request.get(key), str) and re.fullmatch(r"[1-9][0-9]*", request[key]),
                f"Missing run identity: {key}")
    return request


def pinned_revision(text):
    pins = re.findall(r"^[ \t]*GIT_TAG\b([^\r\n]*)", text, re.MULTILINE)
    require(len(pins) == 1, "Dependency must have one immutable full Git SHA")
    pin = re.fullmatch(r"[ \t]+([0-9a-f]{40})[ \t]*(?:#[^\r\n]*)?", pins[0])
    require(pin is not None, "Dependency must have one immutable full Git SHA")
    return pin.group(1)


def prepare(sha, tag):
    require(re.fullmatch(r"[0-9a-f]{40}", sha), "Release requires a full lowercase CLI commit SHA")
    require(git("rev-parse", f"{sha}^{{commit}}") == sha, "Requested object must be a commit")
    # HEAD is the trusted workflow revision on main, not the requested candidate.
    subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=ROOT, check=True)
    request = validate_request({
        "cli_sha": sha, "tag": tag, "version": tag[1:],
        "core_sha": pinned_revision(git("show", f"{sha}:cmake/Core.cmake")),
        "json_sha": pinned_revision(git("show", f"{sha}:cmake/Json.cmake")),
        "workflow_sha": git("rev-parse", "HEAD"),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    })
    require(not git("tag", "--list", tag), "Release tag already exists")
    require(not git("tag", "--points-at", sha, "--list", "v[0-9]*"),
            "CLI commit already has a version tag; each release requires a distinct commit")
    return request


def ctest_results(path):
    root = ET.parse(path).getroot()
    cases = root.findall(".//testcase")
    names = [case.attrib["name"] for case in cases]
    require(len(names) == len(set(names)) and set(names) == TESTS, "Incomplete CTest inventory")
    for case in cases:
        require(case.attrib.get("status") == "run" and
                all(case.find(name) is None for name in ("failure", "error", "skipped")),
                f"CTest did not pass: {case.attrib['name']}")
    return {"tests": len(cases), "passed": len(cases), "failed": 0, "skipped": 0, "names": sorted(names)}


def validate_summary(report, request):
    require(report.get("release_request") == request, "Evidence belongs to a different release request/run")
    require(report.get("cli_revision") == request["cli_sha"] and report.get("cli_dirty") is False,
            "CLI evidence is dirty or from a different revision")
    require(report.get("core_revision") == request["core_sha"] and report.get("core_dirty") is False,
            "Core evidence is dirty or from a different revision")
    require(report.get("json_revision") == request["json_sha"] and report.get("json_dirty") is False,
            "JSON evidence is dirty or from a different revision")
    require(report.get("configuration") == "Release" and report.get("cxx_standard") == 11,
            "Unexpected release build configuration")
    key = (report.get("system"), report.get("shared"))
    require(key in MATRIX, "Unexpected platform/linkage")
    results = report.get("results", [])
    names = [result["case"] for result in results]
    require(len(names) == len(set(names)) and set(names) == BUILD_CASES | REJECTION_CASES,
            "Incomplete dependency scenarios")
    for result in results:
        if result["case"] in REJECTION_CASES:
            require(result["result"] == "passed (rejected)", "Expected rejection did not pass")
            continue
        require(result["result"] == "passed", "Required build did not pass")
        require(result.get("cli_version") == request["version"], "Candidate version not tested")
        require(result.get("baseline_cases") == 154, "Incomplete CLI behavior coverage")
        require(result.get("baseline_failures") == [], "CLI behavior mismatch")
        query = result.get("query", {})
        require(query.get("checks") == 338, "Incomplete Query evidence")
        require(query.get("exclusions") == QUERY_EXCLUSIONS, "Unexpected Query exclusions")
        test = result.get("ctest", {})
        require(test.get("tests") == len(TESTS) and test.get("passed") == len(TESTS) and
                test.get("failed") == 0 and test.get("skipped") == 0 and
                test.get("names") == sorted(TESTS), "Missing, skipped or failed CTest results")
        require(result.get("compiler", {}).get("id") and result["compiler"].get("version"),
                "Missing compiler identity")
    return key


def aggregate(request, directory):
    validate_request(request)
    summaries, matrix = [], set()
    for path in sorted(directory.rglob("summary.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        key = validate_summary(report, request)
        require(key not in matrix, "Duplicate platform/linkage evidence")
        matrix.add(key)
        summaries.append({"path": path.relative_to(directory).as_posix(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "report": report})
    require(matrix == MATRIX, "Missing Windows/Linux static/shared evidence")
    return {"status": "passed", "request": request, "matrix": summaries,
            "builds": len(MATRIX) * len(BUILD_CASES),
            "ctest_passes": len(MATRIX) * len(BUILD_CASES) * len(TESTS)}


def finalize(result, validation, quality):
    result["jobs"] = {"validation": validation, "quality": quality}
    if result.get("status") != "passed" or any(value != "success" for value in result["jobs"].values()):
        result["status"] = "failed"
    return result


def authorize_tag(result, sha, tag, workflow_sha, run_id, run_attempt):
    require(result.get("status") == "passed" and
            result.get("jobs") == {"validation": "success", "quality": "success"},
            "Required release jobs did not pass")
    request = validate_request(result["request"])
    require((request["cli_sha"], request["tag"], request["workflow_sha"],
             request["run_id"], request["run_attempt"]) == (sha, tag, workflow_sha, run_id, run_attempt),
            "Release evidence does not authorize this tag/run")
    require(result.get("builds") == 20 and result.get("ctest_passes") == 220,
            "Release evidence lacks the complete build matrix")
    return {"ref": f"refs/tags/{tag}", "sha": sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--sha", required=True)
    prep.add_argument("--tag", required=True)
    prep.add_argument("--output", type=Path, required=True)
    gate = sub.add_parser("aggregate")
    gate.add_argument("--request", type=Path, required=True)
    gate.add_argument("--evidence", type=Path, required=True)
    gate.add_argument("--output", type=Path, required=True)
    finish = sub.add_parser("finalize")
    finish.add_argument("--output", type=Path, required=True)
    finish.add_argument("--validation", required=True)
    finish.add_argument("--quality", required=True)
    authorize = sub.add_parser("authorize")
    authorize.add_argument("--result", type=Path, required=True)
    authorize.add_argument("--sha", required=True)
    authorize.add_argument("--tag", required=True)
    authorize.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"status": "failed"}
    try:
        if args.command == "prepare":
            result = prepare(args.sha, args.tag)
        elif args.command == "aggregate":
            result = aggregate(json.loads(args.request.read_text(encoding="utf-8")), args.evidence)
        elif args.command == "finalize":
            previous = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else result
            result = finalize(previous, args.validation, args.quality)
            if os.environ.get("GITHUB_STEP_SUMMARY"):
                with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
                    stream.write(f"CLI release validation: **{result['status']}**\n\n"
                                 "See `release-result` for revisions, configurations and test counts.\n")
        else:
            result = authorize_tag(json.loads(args.result.read_text(encoding="utf-8")), args.sha, args.tag,
                                   os.environ.get("GITHUB_SHA"), os.environ.get("GITHUB_RUN_ID"),
                                   os.environ.get("GITHUB_RUN_ATTEMPT"))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        result = {"status": "failed", "error": str(error)}
        print(f"Release gate: {error}", file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.command == "prepare" and result.get("status") != "failed" and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write(f"cli_sha={result['cli_sha']}\n")
    return result.get("status") == "failed"


if __name__ == "__main__":
    sys.exit(main())
