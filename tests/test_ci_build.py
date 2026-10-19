# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Build evidence uses actual public target selection, not an assumed cache variable."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cli_build import core_source
from release import ctest_results


class BuildEvidence(unittest.TestCase):
    def test_source_identity_comes_from_public_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tests').mkdir()
            source = root / 'core'
            selected = root / 'tests/core-selection.txt'
            selected.write_text(f'source\n{source}\n{source / "tlv"}\n{source / "tlv++"}\nFALSE\n')
            self.assertEqual(core_source(root), source.resolve())
            selected.write_text(f'source\n{source}\n{root / "outside"}\n{source / "tlv++"}\nFALSE\n')
            with self.assertRaises(ValueError):
                core_source(root)
            selected.write_text('package\n\n\n\nTRUE\n')
            with self.assertRaises(ValueError):
                core_source(root)

    def test_main_smoke_requires_all_three_tests(self):
        expected = {'core_c_smoke', 'core_cxx_smoke', 'cli_version'}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ctest.xml'
            path.write_text('<testsuite>' + ''.join(f'<testcase name="{name}" status="run" />'
                                                   for name in expected) + '</testsuite>')
            self.assertEqual(ctest_results(path, expected)['passed'], 3)
            path.write_text('<testsuite><testcase name="cli_version" status="run" /></testsuite>')
            with self.assertRaises(ValueError):
                ctest_results(path, expected)


if __name__ == '__main__':
    unittest.main()
