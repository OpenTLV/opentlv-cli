# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Analyze CLI-owned translation units with their real compilation flags."""

import argparse
from pathlib import Path

from ci_support import ROOT, read, require, run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    files = {Path(item['file']).resolve() for item in read(args.build / 'compile_commands.json')
             if Path(item['file']).resolve().is_relative_to(ROOT / 'src')}
    require(files == set((ROOT / 'src').rglob('*.cpp')), 'Incomplete CLI compilation database')
    for source in sorted(files):
        run('clang-tidy-18', '-quiet', '-p', args.build, '--warnings-as-errors=*',
            '--header-filter=' + str(ROOT / 'src'), source)
