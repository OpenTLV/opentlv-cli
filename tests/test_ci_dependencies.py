# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Dependency snapshots must describe resolved targets and the exact successful build."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ci_support import identity, pin
from dependency_snapshot import package_url, resolved_dependencies, snapshot, main

ENV = {'GITHUB_REPOSITORY': 'OpenTLV/opentlv-cli', 'GITHUB_SHA': 'a' * 40,
       'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2', 'GITHUB_REF': 'refs/heads/main',
       'GITHUB_EVENT_NAME': 'push'}


class Dependencies(unittest.TestCase):
    def test_cmake_observations_include_header_only_links_and_reject_unknown_edges(self):
        for imported in (False, True):
            with self.subTest(imported=imported):
                self.check_cmake_observations(imported)

    def check_cmake_observations(self, imported):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(Graph NONE)\n'
                f'add_library(tlv INTERFACE {"IMPORTED" if imported else ""})\n'
                'add_library(OpenTLV::tlv ALIAS tlv)\n'
                f'add_library(tlvpp INTERFACE {"IMPORTED" if imported else ""})\n'
                'add_library(OpenTLV::tlv++ ALIAS tlvpp)\n'
                'target_link_libraries(tlvpp INTERFACE "$<LINK_ONLY:tlv>")\n'
                'add_library(json INTERFACE)\nadd_library(nlohmann_json::nlohmann_json ALIAS json)\n'
                'add_library(otlv INTERFACE)\n'
                'target_link_libraries(otlv INTERFACE OpenTLV::tlv++ nlohmann_json::nlohmann_json)\n'
                f'include("{(ROOT / "cmake/Dependencies.cmake").as_posix()}")\n', encoding='utf-8')
            build = root / 'build'
            result = subprocess.run(['cmake', '-S', str(root), '-B', str(build), '-G', 'Ninja',
                                     '-DCMAKE_BUILD_TYPE=Release'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            core = {'mode': 'pinned-git', 'commit': pin('Core')}
            dependencies = resolved_dependencies(build, 'Release', core, root)
            self.assertEqual(set(dependencies), {'Core', 'Json'})
            self.assertTrue(dependencies['Json']['package_url'].endswith('@' + pin('Json')))
            self.assertEqual(dependencies['Core']['dependencies'], [])
            with self.assertRaisesRegex(ValueError, 'verified checkout'):
                resolved_dependencies(build, 'Release', core, root / 'wrong-json')
            report = build / 'cli-dependencies-Release.txt'
            original = report.read_text(encoding='utf-8')
            for edge in ('unknown_library', '$<UNSUPPORTED:thing>'):
                # Add the edge to the facade's evaluated interface, independently
                # of CMake aliases or which targets have physical link artifacts.
                lines = original.splitlines()
                lines[9] += ';' + edge
                report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Unresolved dependency edge'):
                    resolved_dependencies(build, 'Release', core, root)

    def evidence(self):
        names = sorted(('core_c_smoke', 'core_cxx_smoke', 'cli_version', 'cli_static_core'))
        return {'schema': 1, **identity(), 'configuration': 'Release', 'core_linkage': 'static',
                'sanitizer': False, 'core': {'mode': 'verified-source', 'verified': True, 'commit': pin('Core')},
                'json_commit': pin('Json'),
                'dependencies': {name: {'package_url': package_url(name), 'relationship': 'direct',
                                        'scope': 'runtime', 'dependencies': []} for name in ('Core', 'Json')},
                'reports': {'ctest': {'names': names, 'tests': 4, 'passed': 4, 'failed': 0, 'skipped': 0}}}

    def test_snapshot_preserves_identity_and_has_stable_correlator(self):
        with patch.dict(os.environ, ENV):
            value = snapshot(self.evidence())
            self.assertEqual(value['sha'], ENV['GITHUB_SHA'])
            self.assertEqual(value['ref'], ENV['GITHUB_REF'])
            self.assertEqual(value['job']['id'], '123-2')
            self.assertEqual(value['job']['correlator'], 'cli-main-dependencies')
            self.assertEqual(set(value['manifests']['CMakeLists.txt']['resolved']), {'Core', 'Json'})

    def test_reject_stale_partial_local_or_mismatched_evidence(self):
        with patch.dict(os.environ, ENV):
            valid = self.evidence()
            for key in ('commit', 'run_id', 'run_attempt', 'repository', 'dependencies', 'json_commit', 'reports'):
                invalid = copy.deepcopy(valid)
                invalid[key] = None
                with self.subTest(key=key), self.assertRaises(ValueError):
                    snapshot(invalid)
            for mode, verified in (('local-source', True), ('verified-binary', False), ('verified-source', False)):
                invalid = copy.deepcopy(valid)
                invalid['core'].update(mode=mode, verified=verified)
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    snapshot(invalid)
            invalid = copy.deepcopy(valid)
            invalid['dependencies']['Core']['package_url'] = 'pkg:github/opentlv/opentlv@main'
            with self.assertRaises(ValueError):
                snapshot(invalid)
            for field in ('failed', 'skipped'):
                invalid = copy.deepcopy(valid)
                invalid['reports']['ctest'][field] = 1
                with self.assertRaises(ValueError):
                    snapshot(invalid)

    def test_submission_rejects_pr_forks_and_non_main_before_writes(self):
        for changed in ({'GITHUB_EVENT_NAME': 'pull_request'}, {'GITHUB_REPOSITORY': 'fork/opentlv-cli'},
                        {'GITHUB_REF': 'refs/heads/feature'}):
            with patch.dict(os.environ, ENV | changed), \
                    patch.object(sys, 'argv', ['snapshot', '--evidence', 'unused', '--output', 'unused', '--submit']), \
                    patch('dependency_snapshot.run', return_value=ENV['GITHUB_SHA']) as command, \
                    self.assertRaisesRegex(ValueError, 'canonical Main'):
                main()
            self.assertEqual(command.call_count, 1)

    def test_submission_serializes_validated_payload_and_retains_response(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, ENV):
            root = Path(tmp)
            evidence = root / 'build-evidence.json'
            evidence.write_text(json.dumps(self.evidence()), encoding='utf-8')
            output = root / 'snapshot.json'
            with patch.object(sys, 'argv', ['snapshot', '--evidence', str(evidence),
                                           '--output', str(output), '--submit']), \
                    patch('dependency_snapshot.run', side_effect=[ENV['GITHUB_SHA'], '{"id": 123}']) as command:
                main()
            submitted = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(submitted['sha'], ENV['GITHUB_SHA'])
            self.assertEqual(submitted['manifests']['CMakeLists.txt']['resolved'], self.evidence()['dependencies'])
            request = command.call_args.args
            self.assertIn('repos/OpenTLV/opentlv-cli/dependency-graph/snapshots', request)
            self.assertEqual(request[request.index('--input') + 1], output)
            self.assertEqual(json.loads(output.with_suffix('.response.json').read_text()), {'id': 123})


if __name__ == '__main__':
    unittest.main()
