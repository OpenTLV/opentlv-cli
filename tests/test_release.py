#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Release gates must reject incomplete, stale and unsuccessful evidence."""

import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release import (BUILD_CASES, MATRIX, QUERY_EXCLUSIONS, REJECTION_CASES, TESTS,
                     aggregate, authorize_tag, ctest_results, finalize, pinned_revision, prepare,
                     validate_request, validate_summary)


def request():
    return {"cli_sha": "a" * 40, "core_sha": "b" * 40, "json_sha": "c" * 40,
            "workflow_sha": "d" * 40, "tag": "v0.1.0", "version": "0.1.0",
            "run_id": "123", "run_attempt": "1"}


def summary(system="Linux", shared="ON"):
    return {"release_request": request(), "cli_revision": "a" * 40, "cli_dirty": False,
            "core_revision": "b" * 40, "core_dirty": False, "json_revision": "c" * 40,
            "json_dirty": False, "system": system, "shared": shared,
            "configuration": "Release", "cxx_standard": 11,
            "results": [{"case": name, "result": "passed", "cli_version": "0.1.0",
                         "baseline_cases": 154, "baseline_failures": [],
                         "query": {"checks": 338, "exclusions": QUERY_EXCLUSIONS},
                         "compiler": {"id": "GNU", "version": "14.2"},
                         "ctest": {"tests": len(TESTS), "passed": len(TESTS), "failed": 0,
                                   "skipped": 0, "names": sorted(TESTS)}} for name in sorted(BUILD_CASES)] +
                       [{"case": name, "result": "passed (rejected)"} for name in sorted(REJECTION_CASES)]}


class ReleaseGate(unittest.TestCase):
    def prepare_fixture(self, *, existing_tag=False, tagged_commit=False, ancestor=True):
        def fake_git(*args):
            if args == ("rev-parse", "HEAD"):
                return "d" * 40
            if args == ("rev-parse", "a" * 40 + "^{commit}"):
                return "a" * 40
            if args[0] == "show":
                self.assertTrue(args[1].startswith("a" * 40 + ":cmake/"))
                return "GIT_TAG " + ("b" if args[1].endswith("Core.cmake") else "c") * 40
            if args == ("tag", "--list", "v0.1.0"):
                return "v0.1.0" if existing_tag else ""
            if args == ("tag", "--points-at", "a" * 40, "--list", "v[0-9]*"):
                return "v0.0.1" if tagged_commit else ""
            self.fail(f"Unexpected Git lookup: {args}")
        with patch("release.git", side_effect=fake_git), patch("release.subprocess.run") as run:
            if not ancestor:
                run.side_effect = subprocess.CalledProcessError(1, "git merge-base")
            with patch.dict(os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}):
                result = prepare("a" * 40, "v0.1.0")
            self.assertEqual(run.call_args.args[0], ["git", "merge-base", "--is-ancestor", "a" * 40, "HEAD"])
            return result

    def test_prepare_binds_candidate_pins_and_workflow_revision(self):
        self.assertEqual(self.prepare_fixture(), request())

    def test_prepare_rejects_existing_tags_and_unmerged_commits(self):
        for option in ("existing_tag", "tagged_commit"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.prepare_fixture(**{option: True})
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare_fixture(ancestor=False)

    def test_valid_request_and_prerelease(self):
        self.assertEqual(validate_request(request()), request())
        r = dict(request(), tag="v1.0.0-rc.1", version="1.0.0-rc.1")
        self.assertEqual(validate_request(r), r)

    def test_invalid_input(self):
        for key, value in (("cli_sha", "main"), ("core_sha", "abc123"), ("tag", "v01.2.3"),
                           ("tag", "v1.2.3-rc.01"), ("tag", "v1.2.3;echo bad"),
                           ("version", "0.2.0"), ("run_id", ""), ("run_attempt", "0")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_request(dict(request(), **{key: value}))

    def test_only_immutable_dependency_pin(self):
        self.assertEqual(pinned_revision(" GIT_TAG " + "a" * 40 + "\n"), "a" * 40)
        for text in ("GIT_TAG main", "GIT_TAG " + "a" * 39, "GIT_TAG " + "a" * 41,
                     ("GIT_TAG " + "a" * 40 + "\n") * 2):
            with self.subTest(text=text), self.assertRaises(ValueError):
                pinned_revision(text)

    def test_valid_summary(self):
        self.assertEqual(validate_summary(summary(), request()), ("Linux", "ON"))

    def test_stale_or_dirty_provenance(self):
        for key, value in (("cli_revision", "f" * 40), ("core_revision", "f" * 40),
                           ("json_revision", "f" * 40), ("cli_dirty", True), ("core_dirty", True),
                           ("json_dirty", True), ("configuration", "Debug"), ("cxx_standard", 17),
                           ("system", "Darwin"), ("release_request", dict(request(), run_attempt="2"))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_summary(dict(summary(), **{key: value}), request())

    def test_missing_or_duplicate_scenarios(self):
        for mode in ("missing", "duplicate", "skipped"):
            report = summary()
            if mode == "missing":
                report["results"].pop()
            elif mode == "duplicate":
                report["results"].append(report["results"][0])
            else:
                report["results"][0]["result"] = "skipped"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_summary(report, request())

    def test_test_failures_and_missing_counts(self):
        for key, value in (("baseline_cases", 153), ("baseline_failures", ["failure"]),
                           ("cli_version", "0.7.1"), ("ctest", {}), ("compiler", {}),
                           ("query", {"checks": 336, "exclusions": QUERY_EXCLUSIONS}),
                           ("query", {"checks": 338, "exclusions": []})):
            report = summary()
            report["results"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_summary(report, request())
        for key in ("skipped", "failed"):
            report = summary()
            report["results"][0]["ctest"][key] = 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_summary(report, request())

    def test_all_four_jobs_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (system, shared) in enumerate(sorted(MATRIX)):
                path = root / str(index) / "summary.json"
                path.parent.mkdir()
                path.write_text(json.dumps(summary(system, shared)), encoding="utf-8")
                if index < 3:
                    with self.assertRaises(ValueError):
                        aggregate(request(), root)
            result = aggregate(request(), root)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["ctest_passes"], 220)
            duplicate = root / "extra/summary.json"
            duplicate.parent.mkdir()
            duplicate.write_bytes(path.read_bytes())
            with self.assertRaises(ValueError):
                aggregate(request(), root)

    def test_junit_requires_every_test_to_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ctest.xml"
            cases = [f'<testcase name="{name}" status="run"/>' for name in sorted(TESTS)]
            path.write_text("<testsuite>" + "".join(cases) + "</testsuite>", encoding="utf-8")
            self.assertEqual(ctest_results(path)["passed"], len(TESTS))
            for replacement in ("", cases[1], cases[0].replace('status="run"', 'status="notrun"'),
                                cases[0].replace("/>", "><failure/></testcase>"),
                                cases[0].replace("/>", "><skipped/></testcase>")):
                path.write_text("<testsuite>" + replacement + "".join(cases[1:]) + "</testsuite>", encoding="utf-8")
                with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                    ctest_results(path)

    def test_tag_authorization_requires_successful_jobs_and_matching_request(self):
        result = {"status": "passed", "request": request(), "builds": 20, "ctest_passes": 220}
        with self.assertRaises(ValueError):
            authorize_tag(result, "a" * 40, "v0.1.0", "d" * 40, "123", "1")
        finalize(result, "success", "success")
        self.assertEqual(authorize_tag(result, "a" * 40, "v0.1.0", "d" * 40, "123", "1"),
                         {"ref": "refs/tags/v0.1.0", "sha": "a" * 40})
        valid = ["a" * 40, "v0.1.0", "d" * 40, "123", "1"]
        for index in range(len(valid)):
            changed = valid.copy()
            changed[index] = "different"
            with self.subTest(index=index), self.assertRaises(ValueError):
                authorize_tag(result, *changed)
        for validation, quality in (("failure", "success"), ("success", "failure"),
                                    ("cancelled", "success"), ("success", "skipped")):
            finalized = finalize(dict(result), validation, quality)
            self.assertEqual(finalized["status"], "failed")
            with self.assertRaises(ValueError):
                authorize_tag(finalized, *valid)

    def test_finalizer_cannot_promote_failed_evidence(self):
        result = finalize({"status": "failed"}, "success", "success")
        self.assertEqual(result["status"], "failed")


if __name__ == "__main__":
    unittest.main()
