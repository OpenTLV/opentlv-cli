# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Build evidence uses actual public target selection, not an assumed cache variable."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cli_build import SMOKE, built_executable, core_source
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

    def test_main_smoke_requires_linkage_and_version_tests(self):
        expected = {'core_c_smoke', 'core_cxx_smoke', 'cli_version', 'cli_static_core'}
        self.assertEqual(set(SMOKE), expected)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ctest.xml'
            path.write_text('<testsuite>' + ''.join(f'<testcase name="{name}" status="run" />'
                                                   for name in expected) + '</testsuite>')
            self.assertEqual(ctest_results(path, expected)['passed'], 4)
            path.write_text('<testsuite><testcase name="cli_version" status="run" /></testsuite>')
            with self.assertRaises(ValueError):
                ctest_results(path, expected)

    def test_build_evidence_requires_static_core_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = root / 'cli-package-paths-Release.txt'
            paths.write_text(f'{sys.executable}\n{root / "tlv.dll"}\nSHARED_LIBRARY\n')
            with self.assertRaisesRegex(ValueError, 'static OpenTLV::tlv'):
                built_executable(root, 'Release')
            # A real platform executable without Core imports passes the binary check.
            paths.write_text(f'{sys.executable}\n{root / "tlv.lib"}\nSTATIC_LIBRARY\n')
            self.assertEqual(built_executable(root, 'Release'), Path(sys.executable))


if __name__ == '__main__':
    unittest.main()
