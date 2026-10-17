#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Analyze CLI sources; the compiler validates the required public Core capabilities."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    subprocess.run(["cppcheck", "--version"], check=True)
    subprocess.run(["cppcheck", "--enable=warning,performance,portability", "--error-exitcode=1",
                    "--std=c++11", "--inline-suppr", "--suppress=missingIncludeSystem",
                    "--force", "--check-level=normal",
                    # Normal-depth analysis keeps PR checks bounded. This diagnostic
                    # describes that limit; it is not a source-code finding.
                    "--suppress=normalCheckLevelMaxBranches",
                    # This translation unit only rejects unsupported configurations.
                    # It is compiled in every build and intentionally contains #error.
                    "-isrc/core_requirements.cpp", "src"], cwd=ROOT, check=True)
