#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Compare frozen migration evidence, with the explicit issue #4 version contract."""

import argparse
import json
from pathlib import Path
import sys

from baseline.run import differences, execute_case, read_suite

HERE = Path(__file__).resolve().parent


def version_observation(version):
    return {"exit": 0, "stdout": f"OpenTLV CLI {version}\n", "stderr": "", "files": {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    suite, identity = read_suite(HERE / "baseline/cases.json")
    baseline = json.loads((HERE / "baseline/expected.json").read_text(encoding="utf-8"))
    if baseline["suite_sha256"] != identity or baseline["version"] != 1:
        raise ValueError("Frozen baseline identity mismatch")
    if any(baseline["origin"][k] != v for k, v in suite["origin"].items()):
        raise ValueError("Frozen baseline origin mismatch")
    if set(baseline["observations"]) != {c["id"] for c in suite["cases"]}:
        raise ValueError("Frozen baseline inventory mismatch")
    observations, failures = {}, []
    for case in suite["cases"]:
        expected = baseline["observations"][case["id"]]
        if case["id"] == "version":
            expected = version_observation(args.version)
        actual = execute_case([str(args.cli.resolve())], case)
        observations[case["id"]] = actual
        changed = differences(expected, actual)
        if changed:
            failures.append({"case": case["id"], "fields": changed})
    report = {"suite_sha256": identity, "observations": observations, "failures": failures,
              "intentional_changes": {"version": {"issue": 4, "expected": version_observation(args.version)}}}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{len(observations)} CLI cases: 153 frozen observations and issue #4 version; failures: {failures}")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
