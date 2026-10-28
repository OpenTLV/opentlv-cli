# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Reject incomplete gates, stale evidence and malformed release inputs."""

import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cli_ci import JOBS, PR, check_full, check_results, closed_changelog, configuration, preflight
from ci_support import identity
from verified_core import lock

ENV = {'GITHUB_REPOSITORY': 'OpenTLV/opentlv-cli', 'GITHUB_SHA': 'a' * 40,
       'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2', 'RELEASE_TAG': 'v0.2.0'}


class Gates(unittest.TestCase):
    def test_each_required_job_rejects_failed_cancelled_skipped_or_missing(self):
        for tier in ('pr', 'main', 'full'):
            names = {'smoke'} if tier == 'main' else JOBS
            required = PR if tier == 'pr' else names
            results = {name: {'result': 'success' if name in required else 'skipped'} for name in names}
            check_results(results, tier)
            for name in required:
                for state in ('failure', 'cancelled', 'skipped', None):
                    invalid = copy.deepcopy(results)
                    invalid[name]['result'] = state
                    with self.subTest(tier=tier, name=name, state=state), self.assertRaises(ValueError):
                        check_results(invalid, tier)
                invalid = copy.deepcopy(results)
                del invalid[name]
                with self.assertRaises(ValueError):
                    check_results(invalid, tier)

    def test_full_evidence_exact_identity_and_configuration(self):
        with patch.dict(os.environ, ENV):
            record = {'schema': 2, 'tier': 'full', **identity(), 'configuration': configuration('full'),
                      'checks': {name: 'success' for name in JOBS}}
            check_full(record)
            for key in ('schema', 'tier', 'commit', 'repository', 'run_id', 'run_attempt', 'configuration'):
                invalid = copy.deepcopy(record)
                invalid[key] = None
                with self.subTest(key=key), self.assertRaises(ValueError):
                    check_full(invalid)

    def test_changelog_uses_unprefixed_version_and_isolates_release_notes(self):
        text = '# Changelog\n\n## [0.2.0] - 2026-10-28\n\n### Changed\n\n- CLI quality gates.\n'
        history = '\n## [0.1.0] - 2026-10-18\n\n### Added\n\n- Historical changes.\n'
        self.assertEqual(closed_changelog(text + history, 'v0.2.0'), '### Changed\n\n- CLI quality gates.\n')
        self.assertEqual(closed_changelog(text.replace('0.2.0', '0.2.0-rc.1'), 'v0.2.0-rc.1'),
                         '### Changed\n\n- CLI quality gates.\n')
        for invalid in (text.replace('0.2.0', 'v0.2.0'), text.replace('0.2.0', '0.3.0'),
                        text + '**Unreleased**\n',
                        text.replace('2026-10-28', '2026-02-30'), text.replace('- CLI quality gates.', '') + history):
            with self.assertRaises(ValueError):
                closed_changelog(invalid, 'v0.2.0')
        with self.assertRaises(ValueError):
            closed_changelog(text, '0.2.0')

    def test_release_cannot_dispatch_from_pr_branch_or_fork(self):
        for ref, event, repo in [('refs/heads/feature', 'workflow_dispatch', 'OpenTLV/opentlv-cli'),
                                 ('refs/heads/main', 'push', 'OpenTLV/opentlv-cli'),
                                 ('refs/heads/main', 'workflow_dispatch', 'someone/fork')]:
            with patch.dict(os.environ, ENV | {'GITHUB_REF': ref, 'GITHUB_EVENT_NAME': event,
                                              'GITHUB_REPOSITORY': repo}), self.assertRaises(ValueError):
                preflight('v0.2.0')

    def test_preflight_writes_only_current_release_notes(self):
        environment = ENV | {'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'workflow_dispatch'}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, environment):
            root = Path(tmp)
            (root / 'CHANGELOG.md').write_text(
                '# Changelog\n\n## [0.2.0] - 2026-10-28\n\n### Changed\n\n- Core v0.8.0.\n'
                '\n## [0.1.0] - 2026-10-18\n\n### Added\n\n- Historical changes.\n', encoding='utf-8')
            core_release = {'release_id': 7, 'manifest_sha256': 'd' * 64}
            with patch('cli_ci.ROOT', root), patch('cli_ci.run', return_value=''), \
                    patch('cli_ci.prepare', return_value={'workflow_sha': ENV['GITHUB_SHA']}), \
                    patch('cli_ci.lock', return_value={'release_tag': 'v0.8.0'}), \
                    patch('cli_ci.authenticated_release', return_value=(None, None, None, core_release)):
                candidate = preflight('v0.2.0')
            self.assertEqual(candidate['core_release'], core_release)
            self.assertEqual((root / 'build/release-notes.md').read_text(encoding='utf-8'),
                             '### Changed\n\n- Core v0.8.0.\n')

    def test_unpublished_core_is_development_only(self):
        value = {'schema': 1, 'repository': 'OpenTLV/opentlv', 'commit': 'b' * 40,
                 'release_tag': None, 'allow_verified_source': True}
        with patch('verified_core.read', return_value=value), patch('verified_core.pin', return_value='b' * 40):
            self.assertEqual(lock(), value)
            with self.assertRaises(ValueError):
                lock(True)
            value['commit'] = 'c' * 40
            with self.assertRaises(ValueError):
                lock()


if __name__ == '__main__':
    unittest.main()
