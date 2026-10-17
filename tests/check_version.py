#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Check the public version interface, including exit status and stderr."""

import subprocess
import sys
from pathlib import Path


def check(cli, version):
    result = subprocess.run([cli, "--version"], capture_output=True, text=True, check=False)
    if result.returncode or result.stderr or result.stdout != f"OpenTLV CLI {version}\n":
        raise ValueError(f"CLI version contract failed: {result}")


if __name__ == "__main__":
    check(sys.argv[1], Path(sys.argv[2]).read_text(encoding="utf-8").strip())
