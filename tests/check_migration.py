#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Verify frozen regression inputs; optionally audit every original code import."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-imports", action="store_true",
                        help="also check the initial source import before subsequent CLI changes")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "tests/migration.json").read_text(encoding="utf-8"))
    checked = 0
    for item in manifest["files"]:
        if not (item["frozen"] or args.all_imports):
            continue
        data = (ROOT / item["path"]).read_bytes()
        # Text checkouts may use CRLF; binary fixtures never undergo normalization.
        if not item["path"].endswith(".bin"):
            data = data.replace(b"\r\n", b"\n")
        expected = item.get("import_sha256", item["sha256"])
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit(f"Migration provenance mismatch: {item['path']}")
        checked += 1
    print(f"{checked} migration files match the recorded Core import")


if __name__ == "__main__":
    main()
