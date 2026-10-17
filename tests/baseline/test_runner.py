#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Test the migration comparator's failure boundaries independently of otlv."""

import copy
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from run import differences, execute_case, main, read_suite, relative_file


class BaselineContract(unittest.TestCase):
    def test_only_text_crlf_is_normalized(self):
        before = {"exit": 0, "stdout": "a\r\n", "stderr": "b\r\n", "files": {"x": "0d0a"}}
        after = dict(before, stdout="a\n", stderr="b\n")
        self.assertEqual(differences(before, after), [])
        for field, value in (("exit", 1), ("stdout", "a \n"), ("stderr", ""),
                             ("files", {"x": "0a"}), ("extra", "ignored?")):
            with self.subTest(field=field):
                self.assertEqual(differences(before, dict(after, **{field: value})), [field])
        self.assertEqual(differences({"stdout_hex": "0d0a"}, {"stdout_hex": "0a"}), ["stdout_hex"])

    def test_process_input_streams_exit_and_files_are_preserved(self):
        script = ("import sys; from pathlib import Path; "
                  "data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data); "
                  "sys.stderr.write('diagnostic\\n'); Path('out.bin').write_bytes(data); "
                  "sys.exit(5)")
        actual = execute_case([sys.executable, "-c", script],
                              {"argv": [], "stdin_hex": "0a0d1aff", "binary_stdout": True,
                               "files": {"original.bin": "ab"}})
        self.assertEqual(actual["exit"], 5)
        self.assertEqual(actual["stdout_hex"], "0a0d1aff")
        self.assertEqual(actual["stderr"].replace("\r\n", "\n"), "diagnostic\n")
        self.assertEqual(actual["files"], {"original.bin": "ab", "out.bin": "0a0d1aff"})

    def test_fixture_paths_cannot_escape_the_case(self):
        for name in ("../x", "/x", "C:/x", "a\\b", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relative_file(Path("case"), name)

    def test_suite_identity_includes_inputs_and_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            suite = {"version": 1, "cases": [{"id": "one", "argv": [], "stdin_hex": "00"}]}
            path.write_text(json.dumps(suite), encoding="utf-8")
            original = read_suite(path)[1]
            path.write_text(json.dumps(suite, indent=2), encoding="utf-8")
            self.assertEqual(read_suite(path)[1], original)
            for field, value in (("argv", ["--help"]), ("stdin_hex", "01")):
                modified = copy.deepcopy(suite)
                modified["cases"][0][field] = value
                path.write_text(json.dumps(modified), encoding="utf-8")
                self.assertNotEqual(read_suite(path)[1], original)

    def test_duplicate_ids_and_empty_suites_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for cases in ([], [{"id": "a"}, {"id": "a"}]):
                path.write_text(json.dumps({"version": 1, "cases": cases}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_suite(path)

    def test_compare_rejects_missing_or_stale_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite = root / "suite.json"
            baseline = root / "baseline.json"
            suite.write_text(json.dumps({"version": 1, "origin": {}, "cases": [{"id": "one"}]}), encoding="utf-8")
            for identity in ("stale", read_suite(suite)[1]):
                baseline.write_text(json.dumps({"version": 1, "origin": {}, "suite_sha256": identity,
                                                "observations": {}}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    main(["compare", "--cli", sys.executable, "--suite", str(suite),
                          "--baseline", str(baseline)])

    def test_compare_returns_failure_and_writes_actual_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite, baseline, report = (root / name for name in ("suite.json", "expected.json", "actual.json"))
            suite.write_text(json.dumps({"version": 1, "origin": {}, "cases": [
                {"id": "changed", "argv": ["-c", "print('changed')"], "exit": 0}]}), encoding="utf-8")
            baseline.write_text(json.dumps({"version": 1, "origin": {}, "suite_sha256": read_suite(suite)[1],
                "observations": {"changed": {"exit": 0, "stdout": "original\n", "stderr": "", "files": {}}}}),
                encoding="utf-8")
            before = baseline.read_bytes()
            with redirect_stderr(io.StringIO()):
                result = main(["compare", "--cli", sys.executable, "--suite", str(suite),
                               "--baseline", str(baseline), "--report", str(report)])
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(report.read_text())["failures"][0]["fields"], ["stdout"])
            self.assertEqual(baseline.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
