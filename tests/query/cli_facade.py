# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Applicable common corpus through the public CLI, with explicit provider exclusions."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    cases = json.loads(Path(__file__).with_name("corpus.json").read_text())["cases"]
    checks, excluded = 0, []
    for case in cases:
        # CLI names are supplied by its EMV dictionary, not a fixture registry.
        if "fixture:" in case["query"] or "name(" in case["query"]:
            excluded.append({"id": case["id"], "reason": "requires external fixture name resolver"})
            continue
        for backend in ("auto", "document"):
            command = [args.cli, "query", "--query", case["query"], "--format", "ber",
                       "--hex", case["wire"], "--output", "json", "--diagnostics", "json",
                       "--backend", backend]
            for name, value in case.get("variables", {}).items():
                command += ["--var", f"{name}:{value['type']}={value['value']}"]
            result = subprocess.run(command, text=True, capture_output=True, timeout=30)
            if "diagnostic" in case:
                assert result.returncode != 0, (case["id"], backend)
                diagnostic = json.loads(result.stderr)
                expected = case["diagnostic"]
                for field in ("code", "kind"):
                    if field in expected:
                        assert diagnostic[field] == expected[field], (case["id"], field, diagnostic)
                if "begin" in expected:
                    # The expression span is primary, or related evidence beside another location.
                    location = diagnostic["location"]
                    span = location if location["domain"] == "expression" else diagnostic["expression"]
                    assert (span["begin"], span["end"]) == (expected["begin"], expected["end"]), (case["id"], diagnostic)
            else:
                assert result.returncode in (0, 5), (case["id"], backend, result.stderr)
                output = json.loads(result.stdout)
                expected = case["matches"]
                if isinstance(expected, str):
                    value = output["value"]
                    kind = output["type"]
                    actual = (f"bool:{int(value)}" if kind == 1 else f"int:{value}" if kind == 2
                              else "bytes:" + value.lower() if kind == 3
                              else "string:" + value.encode().hex())
                else:
                    # Both backends retain the wire coordinates of the input.
                    actual = [row["offset"] for row in output["matches"]]
                assert actual == expected, (case["id"], backend, actual, expected)
            checks += 1
    report = {"version": 1, "facade": "CLI", "checks": checks, "exclusions": excluded}
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(report, indent=2) + "\n")
    print(f"CLI public Query facade: {checks} common backend checks, {len(excluded)} provider exclusions")


if __name__ == "__main__":
    main()
