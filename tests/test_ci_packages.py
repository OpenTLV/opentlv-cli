# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Exercise release assembly with complete synthetic producer evidence."""

import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cli_ci import IDS, JOBS, assemble, configuration
from ci_support import digest, identity, read, write
from test_release import request, summary
from test_ci_gates import ENV
from test_ci_metadata import release_metadata
from test_ci_artifacts import fixture_archive
from release_artifacts import SMOKE_CASES, TARGETS, verify_archive


class Packages(unittest.TestCase):
    def exercise(self, change=None):
        environment = ENV | {'GITHUB_SHA': 'a' * 40, 'GITHUB_RUN_ATTEMPT': '1', 'RELEASE_TAG': 'v0.1.0'}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, environment):
            root = Path(tmp)
            candidate = request() | {'core_lock': {'release_tag': 'v0.8.0'}, 'repository': ENV['GITHUB_REPOSITORY'],
                                     'core_release': {'release_id': 7, 'manifest_sha256': 'd' * 64}}
            quality = {'schema': 2, 'tier': 'full', **identity(), 'configuration': configuration('full'),
                       'checks': {name: 'success' for name in JOBS}}
            for identifier in IDS:
                folder = root / 'evidence' / identifier
                folder.mkdir(parents=True)
                system = TARGETS[identifier][0]
                report = summary(system)
                report['release_request'] = candidate
                if system != 'Darwin':
                    write(folder / 'summary.json', report)
                first = report['results'][0]
                package = {'schema': 1, **identity(), 'id': identifier,
                           'configuration': 'Release', 'version': '0.1.0',
                           'core_linkage': 'static', 'sanitizer': False,
                           'json_commit': candidate['json_sha'],
                           'compiler': {'COMPILER_ID': TARGETS[identifier][2],
                                        'SIZEOF_DATA_PTR': '8'},
                           'reports': {'ctest': first['ctest'], 'baseline_cases': 154, 'query': first['query']},
                           'core': {'verified': True, 'mode': 'verified-source',
                                    'release_id': 7, 'manifest_sha256': 'd' * 64,
                                    'commit': candidate['core_sha'], 'release_tag': 'v0.8.0'}}
                package['provenance'] = release_metadata(package)
                archive = fixture_archive(folder, package)
                package.update(filename=archive.name, sha256=digest(archive),
                               package_verification=verify_archive(archive, package) | {
                                   'smoke': {'status': 'passed', 'cases': SMOKE_CASES}})
                write(folder / (identifier + '.json'), package)
            if change:
                change(root)
            with patch('cli_ci.preflight', return_value=candidate):
                assemble(candidate, quality, root / 'evidence', root / 'publish')
            result = read(root / 'result.json')
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['jobs'], {'validation': 'success', 'quality': 'success'})
            self.assertEqual(result['builds'], 10)
            self.assertEqual(result['ctest_passes'], 140)
            self.assertEqual(len(result['artifacts']), 3)
            self.assertEqual(IDS, {'linux-x64-static', 'windows-x64-static', 'macos-arm64-static'})
            checksums = (root / 'publish/SHA256SUMS').read_text().splitlines()
            self.assertEqual(len(checksums), 7)
            for line in checksums:
                checksum, filename = line.split('  ')
                self.assertEqual(checksum, digest(root / 'publish' / filename))

    def test_complete_matrix_preserves_portal_contract(self):
        self.exercise()

    def test_missing_macos_package_blocks_publication(self):
        with self.assertRaisesRegex(ValueError, 'Missing approved CLI packages'):
            self.exercise(lambda root: (root / 'evidence/macos-arm64-static/macos-arm64-static.json').unlink())

    def test_missing_tampered_stale_unverified_or_incomplete_package_rejected(self):
        def change(root, mode):
            folder = root / 'evidence/linux-x64-static'
            path = folder / 'linux-x64-static.json'
            data = read(path)
            if mode == 'missing':
                path.unlink()
                return
            if mode == 'tampered':
                (folder / data['filename']).write_bytes(b'tampered')
                return
            if mode == 'stale':
                data['run_attempt'] = '2'
            if mode == 'unverified':
                data['core']['verified'] = False
            if mode == 'tests':
                data['reports']['ctest']['skipped'] = 1
            if mode == 'changed-core':
                data['core']['manifest_sha256'] = 'e' * 64
            if mode == 'schema':
                data['schema'] = 2
            if mode == 'shared':
                data['core_linkage'] = 'shared'
            if mode == 'provenance':
                del data['provenance']
            if mode == 'smoke':
                data['package_verification']['smoke']['cases'] = ['version']
            if mode == 'inventory':
                data['package_verification']['files'] = {}
            if mode == 'runtime-core':
                data['provenance']['binary']['runtime_imports'].append('tlv.dll')
            write(path, data)
        for mode in ('missing', 'tampered', 'stale', 'unverified', 'tests', 'changed-core', 'schema',
                     'shared', 'provenance', 'runtime-core', 'smoke', 'inventory'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.exercise(lambda root: change(root, mode))


if __name__ == '__main__':
    unittest.main()
