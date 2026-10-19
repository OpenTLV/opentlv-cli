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
                system = 'Windows' if identifier.startswith('windows-') else 'Linux'
                shared = 'ON' if identifier.endswith('-shared') else 'OFF'
                report = summary(system, shared)
                report['release_request'] = candidate
                write(folder / 'summary.json', report)
                extension = '.zip' if system == 'Windows' else '.tar.gz'
                archive = folder / f"OpenTLV-CLI-0.1.0-{identifier}{extension}"
                archive.write_bytes(b'tested archive')
                first = report['results'][0]
                package = {'schema': 1, **identity(), 'id': identifier, 'filename': archive.name,
                           'sha256': digest(archive), 'configuration': 'Release', 'version': '0.1.0',
                           'shared': shared, 'package_cases': 154, 'sanitizer': False,
                           'json_commit': candidate['json_sha'],
                           'compiler': {'COMPILER_ID': 'MSVC' if system == 'Windows' else 'GNU',
                                        'SIZEOF_DATA_PTR': '8'},
                           'reports': {'ctest': first['ctest'], 'baseline_cases': 154, 'query': first['query']},
                           'core': {'verified': True, 'mode': 'verified-source',
                                    'release_id': 7, 'manifest_sha256': 'd' * 64,
                                    'commit': candidate['core_sha'], 'release_tag': 'v0.8.0'}}
                write(folder / (identifier + '.json'), package)
            if change:
                change(root)
            with patch('cli_ci.preflight', return_value=candidate):
                assemble(candidate, quality, root / 'evidence', root / 'publish')
            result = read(root / 'result.json')
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['jobs'], {'validation': 'success', 'quality': 'success'})
            self.assertEqual(result['builds'], 20)
            self.assertEqual(result['ctest_passes'], 220)
            self.assertEqual(len(result['artifacts']), 4)
            self.assertTrue((root / 'publish/SHA256SUMS').is_file())

    def test_complete_matrix_preserves_portal_contract(self):
        self.exercise()

    def test_missing_tampered_stale_unverified_or_incomplete_package_rejected(self):
        def change(root, mode):
            folder = root / 'evidence/linux-x64-shared'
            path = folder / 'linux-x64-shared.json'
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
            write(path, data)
        for mode in ('missing', 'tampered', 'stale', 'unverified', 'tests', 'changed-core', 'schema'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.exercise(lambda root: change(root, mode))


if __name__ == '__main__':
    unittest.main()
