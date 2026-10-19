# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Exercise actual CMake package selection without network or Core compilation."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExplicitPackage(unittest.TestCase):
    def configure(self, *, absent=False, source=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('selected', 'trap'):
                folder = root / name
                folder.mkdir()
                (folder / 'OpenTLVConfig.cmake').write_text(
                    'message(FATAL_ERROR "Unexpected package trap")\n' if name == 'trap' else
                    'add_library(OpenTLV::tlv INTERFACE IMPORTED)\n'
                    'add_library(OpenTLV::tlv++ INTERFACE IMPORTED)\n')
            (root / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(Selection NONE)\n'
                f'include("{(ROOT / "cmake/Core.cmake").as_posix()}")\n')
            args = ['cmake', '-S', str(root), '-B', str(root / 'build'), '-G', 'Ninja',
                    '-DOPENTLV_CLI_CORE_PACKAGE=' + (root / ('absent' if absent else 'selected')).as_posix(),
                    '-DOpenTLV_DIR=' + (root / 'trap').as_posix(),
                    '-DCMAKE_PREFIX_PATH=' + (root / 'trap').as_posix()]
            if source:
                args.append('-DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=' + root.as_posix())
            return subprocess.run(args, capture_output=True, text=True)

    def test_explicit_package_beats_discoverable_package_and_cached_directory(self):
        result = self.configure()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_absent_explicit_package_does_not_fall_back(self):
        result = self.configure(absent=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Selected Core package is missing', result.stderr)

    def test_package_and_source_cannot_be_combined(self):
        result = self.configure(source=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot be combined', result.stderr)


if __name__ == '__main__':
    unittest.main()
