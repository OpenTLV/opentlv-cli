# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Analyze CLI-owned translation units with their real compilation flags."""

import argparse
from pathlib import Path

from ci_support import ROOT, read, require, run

CLANG_TIDY = 'clang-tidy-22'
# clang-tidy's historical built-in default, stated explicitly: newer releases
# enable no checks without a configuration and stop with "no checks enabled".
CHECKS = '-*,clang-diagnostic-*,clang-analyzer-*'


def enabled_checks():
    """Return the enabled check names; compiler diagnostics are not listed."""
    listing = run(CLANG_TIDY, '--checks=' + CHECKS, '--list-checks', capture=True)
    return [line.strip() for line in listing.splitlines() if line.startswith((' ', '\t')) and line.strip()]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    require(any(name.startswith('clang-analyzer-') for name in enabled_checks()),
            CLANG_TIDY + ' provides no clang-analyzer checks; it was built without the Clang Static Analyzer')
    files = {Path(item['file']).resolve() for item in read(args.build / 'compile_commands.json')
             if Path(item['file']).resolve().is_relative_to(ROOT / 'src')}
    require(files == set((ROOT / 'src').rglob('*.cpp')), 'Incomplete CLI compilation database')
    for source in sorted(files):
        run(CLANG_TIDY, '-quiet', '-p', args.build, '--checks=' + CHECKS, '--warnings-as-errors=*',
            '--header-filter=' + str(ROOT / 'src'), source)
