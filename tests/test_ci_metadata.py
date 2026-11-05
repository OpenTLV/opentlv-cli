# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Build provenance works offline, with packages, exports and dirty checkouts."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_metadata import collect, header_identity, main, source_identity, startup, validate_release
from cli_build import package
from ci_support import ROOT, digest, pin, write


def release_metadata(record):
    return {'schema': 1, 'configuration': record['configuration'],
            'cli': {'commit': record['commit'], 'version': record['version'], 'dirty': False},
            'core': {'requested_commit': record['core']['commit'], 'commit': None, 'dirty': None,
                     'library_sha256': 'a' * 64, 'headers': {'sha256': 'b' * 64, 'files': 12}},
            'json': {'commit': record['json_commit'], 'dirty': False, 'version': '3.11.3',
                     'headers': {'sha256': 'c' * 64, 'files': 10}},
            'toolchain': {'CMAKE_SYSTEM_NAME': 'Windows' if record['id'].startswith('windows-') else 'Linux',
                          'CMAKE_SIZEOF_VOID_P': '8', 'CMAKE_C_COMPILER_ID': 'test',
                          'CMAKE_C_COMPILER_VERSION': '1', 'CMAKE_CXX_COMPILER_ID': 'test',
                          'CMAKE_CXX_COMPILER_VERSION': '2'},
            'binary': {'sha256': 'd' * 64, 'core_linkage': 'static', 'runtime_imports': ['libc.so.6'],
                       'startup': {'status': 'passed'}}}


class Metadata(unittest.TestCase):
    def test_collect_records_actual_package_content_without_claiming_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            headers = build / 'include'
            (headers / 'nlohmann').mkdir(parents=True)
            (headers / 'nlohmann/json.hpp').write_text(
                '#define NLOHMANN_JSON_VERSION_MAJOR 3\n#define NLOHMANN_JSON_VERSION_MINOR 11\n'
                '#define NLOHMANN_JSON_VERSION_PATCH 3\n')
            library = build / 'tlv.lib'
            library.write_bytes(b'example static archive')
            inputs = {'configuration': 'Debug', 'source': str(ROOT), 'core_source': '', 'json_source': str(ROOT),
                      'json_imported': 'TRUE',
                      'core_imported': 'TRUE', 'core_type': 'STATIC_LIBRARY', 'core_library': str(library),
                      'core_includes': str(headers), 'json_includes': str(headers),
                      'executable': sys.executable, 'OPENTLV_CLI_SANITIZER': 'none',
                      'CMAKE_CROSSCOMPILING': 'FALSE', 'CMAKE_CXX_COMPILER_ID': 'different-from-C'}
            write(build / 'cli-build-inputs-Debug.json', inputs)
            (build / 'cli-version.txt').write_text('0.0.0+unknown\n')
            (build / 'CMakeCache.txt').write_text('CMAKE_CXX_FLAGS:STRING=-custom\nSECRET:STRING=hidden\n')
            result = collect(build, 'Debug')
            self.assertIsNone(result['core']['commit'])
            self.assertEqual(result['core']['requested_commit'], pin('Core'))
            self.assertEqual(result['core']['library_sha256'], digest(library))
            self.assertEqual(result['json']['version'], '3.11.3')
            self.assertIsNone(result['json']['commit'])
            self.assertEqual(result['json']['selection'], 'package')
            self.assertTrue(result['binary']['runtime_imports'])
            self.assertEqual(result['binary']['startup']['status'], 'not-run')
            self.assertEqual(result['settings'], {'CMAKE_CXX_FLAGS': '-custom'})
            self.assertEqual(result['toolchain']['CMAKE_CXX_COMPILER_ID'], 'different-from-C')
            # A package rebuild changes its immutable content identity.
            library.write_bytes(b'changed archive')
            self.assertNotEqual(collect(build, 'Debug')['core']['library_sha256'], result['core']['library_sha256'])
            inputs['CMAKE_CROSSCOMPILING'] = 'TRUE'
            write(build / 'cli-build-inputs-Debug.json', inputs)
            with self.assertRaisesRegex(ValueError, 'native target environment'):
                collect(build, 'Debug', verify_startup=True)

    def test_export_never_inherits_workspace_revision(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as tmp:
            self.assertEqual(source_identity(tmp), {'commit': None, 'dirty': None})
        actual = source_identity(ROOT)
        self.assertRegex(actual['commit'], '^[0-9a-f]{40}$')
        self.assertIsInstance(actual['dirty'], bool)
        with patch('build_metadata.subprocess.run', side_effect=FileNotFoundError):
            self.assertEqual(source_identity(ROOT), {'commit': None, 'dirty': None})

    def test_headers_identity_survives_relocation_but_detects_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('first', 'relocated'):
                (root / name).mkdir()
                (root / name / 'config.h').write_text('#define FEATURE 1\n')
            original = header_identity(str(root / 'first'))
            self.assertEqual(original, header_identity(str(root / 'relocated')))
            (root / 'relocated/config.h').write_text('#define FEATURE 0\n')
            self.assertNotEqual(original, header_identity(str(root / 'relocated')))

    def test_failed_launch_or_wrong_version_cannot_be_success(self):
        with self.assertRaisesRegex(ValueError, 'startup/version'):
            startup(Path(sys.executable), '0.1.0')
        with patch('build_metadata.subprocess.run', side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                startup(Path(sys.executable), '0.1.0')

    def test_failed_refresh_removes_stale_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'build-info-Release.json'
            write(output, {'binary': {'startup': {'status': 'passed'}}})
            with patch.object(sys, 'argv', ['build_metadata.py', '--build', tmp]), \
                    patch('build_metadata.collect', side_effect=ValueError('invalid binary')):
                with self.assertRaisesRegex(ValueError, 'invalid binary'):
                    main()
            self.assertFalse(output.exists())

    def test_packaging_rejects_binary_changed_after_verification(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch('cli_build.built_executable', return_value=Path(sys.executable)):
            output = Path(tmp) / 'package'
            record = {'configuration': 'Release', 'provenance': {'binary': {'sha256': '0' * 64}}}
            with self.assertRaisesRegex(ValueError, 'Executable changed'):
                package(Path(tmp), output, record)
            self.assertFalse(output.exists())

    def test_release_rejects_incomplete_or_inconsistent_provenance(self):
        record = {'configuration': 'Release', 'commit': 'a' * 40, 'version': '0.1.0',
                  'core': {'commit': pin('Core')}, 'json_commit': pin('Json'), 'id': 'linux-x64-static'}
        valid = release_metadata(record)
        validate_release(valid, record)
        # Full CI also verifies the candidate on macOS, without publishing a package.
        macos = copy.deepcopy(valid)
        macos['toolchain']['CMAKE_SYSTEM_NAME'] = 'Darwin'
        macos['binary']['runtime_imports'] = ['/usr/lib/libSystem.B.dylib']
        validate_release(macos, record | {'id': 'macos-arm64-static'})
        changes = [('cli', 'dirty', True), ('cli', 'commit', 'b' * 40),
                   ('core', 'commit', 'b' * 40), ('core', 'dirty', True),
                   ('core', 'library_sha256', ''), ('json', 'headers', {}),
                   ('json', 'commit', None), ('json', 'dirty', True),
                   ('binary', 'startup', {'status': 'not-run'}), ('binary', 'sha256', ''),
                   ('binary', 'runtime_imports', ['libtlv.so.1']), ('binary', 'runtime_imports', []),
                   ('toolchain', 'CMAKE_CXX_COMPILER_VERSION', ''),
                   ('toolchain', 'CMAKE_SYSTEM_NAME', 'Darwin')]
        for section, key, value in changes:
            bad = copy.deepcopy(valid)
            bad[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                validate_release(bad, record)
        with self.assertRaises(ValueError):
            validate_release({}, record)


if __name__ == '__main__':
    unittest.main()
