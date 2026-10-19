# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Reject incomplete gates, stale evidence and malformed release inputs."""

import copy
import os
from pathlib import Path
import sys
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

    def test_changelog_matches_core_release_convention(self):
        text = '# Changelog\n\n## [v0.2.0] - 2026-10-19\n\n### Changed\n\n- CLI quality gates.\n'
        closed_changelog(text, 'v0.2.0')
        for invalid in (text.replace('v0.2.0', '0.2.0'), text + '**Unreleased**\n',
                        text.replace('2026-10-19', '2026-02-30'), text.replace('- CLI quality gates.', '')):
            with self.assertRaises(ValueError):
                closed_changelog(invalid, 'v0.2.0')

    def test_release_cannot_dispatch_from_pr_branch_or_fork(self):
        for ref, event, repo in [('refs/heads/feature', 'workflow_dispatch', 'OpenTLV/opentlv-cli'),
                                 ('refs/heads/main', 'push', 'OpenTLV/opentlv-cli'),
                                 ('refs/heads/main', 'workflow_dispatch', 'someone/fork')]:
            with patch.dict(os.environ, ENV | {'GITHUB_REF': ref, 'GITHUB_EVENT_NAME': event,
                                              'GITHUB_REPOSITORY': repo}), self.assertRaises(ValueError):
                preflight('v0.2.0')

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
