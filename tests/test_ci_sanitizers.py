# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""A sanitizer gate must reject disabled instrumentation and ordinary crashes."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_executable import ProcessContract
from check_sanitizer import verify


class SanitizerDiagnostics(unittest.TestCase):
    def test_detector_requires_failure_kind_and_source_location(self):
        for mode, diagnostic in (
            ('address', 'AddressSanitizer: heap-use-after-free in sanitizer_probe.cpp:15'),
            ('undefined', 'sanitizer_probe.cpp:10: runtime error: signed integer overflow'),
        ):
            with self.subTest(mode=mode):
                verify(86, diagnostic, mode)
                for code, output in ((0, diagnostic), (-11, 'Segmentation fault'),
                                     (1, diagnostic.replace('sanitizer_probe.cpp', 'unknown')),
                                     (1, 'error loading sanitizer runtime')):
                    with self.assertRaises(ValueError):
                        verify(code, output, mode)

    def test_process_contract_rejects_sanitizer_on_expected_error_path(self):
        case = ProcessContract()
        case.cli = Path('otlv')
        case.work = Path('.')
        for marker in ('AddressSanitizer', 'LeakSanitizer', 'UndefinedBehaviorSanitizer', 'runtime error:'):
            result = subprocess.CompletedProcess([], 1, b'', f'otlv: truncated input\n{marker}'.encode())
            with self.subTest(marker=marker), patch('check_executable.subprocess.run', return_value=result):
                with self.assertRaises(AssertionError):
                    case.invoke('validate', code=1, error='truncated input')


if __name__ == '__main__':
    unittest.main()
