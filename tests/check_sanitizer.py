#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Require a real, symbolized detector report; any crash alone is insufficient."""

import argparse
from pathlib import Path
import subprocess


def verify(returncode, output, mode):
    markers = (('AddressSanitizer', 'heap-use-after-free') if mode == 'address'
               else ('runtime error:', 'signed integer overflow'))
    if returncode == 0 or not all(marker in output for marker in (*markers, 'sanitizer_probe.cpp')):
        raise ValueError(f'{mode} did not produce the expected symbolized diagnostic:\n{output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=('address', 'undefined'))
    parser.add_argument('--log', required=True, type=Path)
    args = parser.parse_args()
    command = [str(args.probe)] + (['overflow'] if args.mode == 'undefined' else [])
    result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(f'exit={result.returncode}\n{output}', encoding='utf-8')
    verify(result.returncode, output, args.mode)
    print(f'{args.mode}: detected deliberate fault with source location; log: {args.log}')


if __name__ == '__main__':
    main()
