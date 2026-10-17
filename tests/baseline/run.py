#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Capture a pinned CLI baseline or compare an executable against it (stdlib only)."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_suite(path):
    raw = path.read_bytes()
    suite = json.loads(raw)
    if suite["version"] != 1 or not suite["cases"]:
        raise ValueError("unsupported or empty suite")
    ids = [case["id"] for case in suite["cases"]]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case IDs")
    # Hash logical JSON so Git's checkout line-ending conversion is harmless.
    identity = digest(json.dumps(suite, sort_keys=True, separators=(",", ":")).encode())
    return suite, identity


def relative_file(root, name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError(f"unsafe fixture path: {name}")
    return root.joinpath(*path.parts)


def execute_case(command, case):
    with tempfile.TemporaryDirectory(prefix="opentlv-cli-baseline-") as directory:
        root = Path(directory)
        for name, value in case.get("files", {}).items():
            path = relative_file(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes.fromhex(value))
        env = dict(os.environ, LC_ALL="C", LANG="C", TERM="dumb", NO_COLOR="1")
        result = subprocess.run(command + case["argv"], cwd=root, env=env,
                                input=bytes.fromhex(case.get("stdin_hex", "")),
                                capture_output=True, timeout=30)
        observation = {"exit": result.returncode,
                       "stderr": result.stderr.decode("utf-8"),
                       "files": {p.relative_to(root).as_posix(): p.read_bytes().hex()
                                 for p in sorted(root.rglob("*")) if p.is_file()}}
        if case.get("binary_stdout", False):
            observation["stdout_hex"] = result.stdout.hex()
        else:
            observation["stdout"] = result.stdout.decode("utf-8")
        return observation


def differences(expected, actual):
    """Only text-stream CRLF/LF differences are permitted; files remain exact."""
    changed = []
    for field in sorted(set(expected) | set(actual)):
        left, right = expected.get(field), actual.get(field)
        if field in ("stdout", "stderr") and isinstance(left, str) and isinstance(right, str):
            left, right = left.replace("\r\n", "\n"), right.replace("\r\n", "\n")
        if left != right:
            changed.append(field)
    return changed


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def provenance(source, build, cli, origin):
    source, build = source.resolve(), build.resolve()
    if git(source, "rev-parse", "HEAD") != origin["commit"]:
        raise ValueError("capture requires the pinned originating commit")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("capture requires an unchanged source checkout")
    if git(source, "rev-list", "-n", "1", origin["nearest_tag"]) != origin["tag_commit"]:
        raise ValueError("originating tag no longer resolves to the recorded commit")
    cache = {}
    for line in (build / "CMakeCache.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "//")) and ":" in line and "=" in line:
            name, value = line.split("=", 1)
            cache[name.split(":", 1)[0]] = value
    if Path(cache["CMAKE_HOME_DIRECTORY"]).resolve() != source:
        raise ValueError("build directory does not belong to the reference checkout")
    cli.relative_to(build)
    compiler_file = next((build / "CMakeFiles").glob("*/CMakeCXXCompiler.cmake"))
    compiler = dict(re.findall(r'set\(CMAKE_CXX_(COMPILER_ID|COMPILER_VERSION) "([^"]+)"\)',
                               compiler_file.read_text(encoding="utf-8")))
    return dict(origin, platform=platform.platform(), compiler=compiler,
                executable_sha256=digest(cli.read_bytes()),
                cmake={k: v for k, v in cache.items() if (k.startswith("OPENTLV_") and v in ("ON", "OFF")) or
                       k in ("CMAKE_BUILD_TYPE", "CMAKE_CXX_STANDARD", "CMAKE_GENERATOR")})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "compare"))
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--suite", type=Path, default=HERE / "cases.json")
    parser.add_argument("--baseline", type=Path, default=HERE / "expected.json")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    suite, identity = read_suite(args.suite)
    cli = args.cli.resolve(strict=True)
    if args.mode == "capture":
        if not args.source or not args.build_dir:
            parser.error("capture requires --source and --build-dir")
        if args.baseline.exists():
            parser.error("capture never overwrites evidence; choose a new --baseline path")
        origin = provenance(args.source, args.build_dir, cli, suite["origin"])
        expected = None
    else:
        expected = json.loads(args.baseline.read_text(encoding="utf-8"))
        if expected["version"] != 1 or expected["suite_sha256"] != identity:
            raise ValueError("baseline suite identity mismatch; do not recapture from the candidate")
        if any(expected["origin"][key] != value for key, value in suite["origin"].items()):
            raise ValueError("baseline origin mismatch")
        if set(expected["observations"]) != {case["id"] for case in suite["cases"]}:
            raise ValueError("baseline case inventory mismatch")
    observations, failures = {}, []
    for case in suite["cases"]:
        actual = execute_case([str(cli)], case)
        observations[case["id"]] = actual
        changed = differences(expected["observations"][case["id"]], actual) if expected else []
        if actual["exit"] != case["exit"] and "exit" not in changed:
            changed.append("exit")
        if changed:
            failures.append({"case": case["id"], "fields": changed, "actual": actual})
            print(f"FAIL {case['id']}: {', '.join(changed)}", file=sys.stderr)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"suite_sha256": identity, "failures": failures,
                                          "observations": observations}, indent=2) + "\n", encoding="utf-8")
    if failures:
        return 1
    if not expected:
        with args.baseline.open("x", encoding="utf-8", newline="\n") as output:
            json.dump({"version": 1, "suite_sha256": identity, "origin": origin,
                       "observations": observations}, output, ensure_ascii=True, indent=2)
            output.write("\n")
    print(f"{len(observations)} CLI baseline cases {'captured' if not expected else 'matched'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"CLI baseline: {error}", file=sys.stderr)
        sys.exit(1)
