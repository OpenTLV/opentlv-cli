# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Workflow ownership/routing contract, including the publication boundary."""

from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from cli_ci import JOBS


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'))


def triggers(value):
    # PyYAML's YAML 1.1 resolver treats the unquoted Actions key 'on' as true.
    return value.get('on', value.get(True))


class Workflows(unittest.TestCase):
    def test_four_entry_points_match_core_routing(self):
        self.assertEqual(set(triggers(workflow('cli-pr.yml'))), {'pull_request'})
        self.assertEqual(set(triggers(workflow('cli-main.yml'))), {'push'})
        self.assertEqual(set(triggers(workflow('cli-full.yml'))), {'workflow_dispatch', 'workflow_call'})
        self.assertEqual(set(triggers(workflow('release.yml'))), {'workflow_dispatch'})
        self.assertFalse((ROOT / '.github/workflows/core-dependency.yml').exists())

    def test_gate_cannot_skip_failed_workers(self):
        gate = workflow('cli-checks.yml')['jobs']['gate']
        self.assertEqual(gate['if'], 'always()')
        self.assertEqual(set(gate['needs']), JOBS)
        full = workflow('cli-full.yml')['jobs']['checks']
        self.assertIs(full['with']['full'], True)

    def test_release_has_only_tag_and_requires_full_before_binaries_and_publication(self):
        release = workflow('release.yml')
        self.assertEqual(set(triggers(release)['workflow_dispatch']['inputs']), {'tag'})
        self.assertEqual(release['jobs']['full']['needs'], 'candidate')
        self.assertEqual(release['jobs']['binaries']['needs'], 'full')
        self.assertEqual(set(release['jobs']['publish']['needs']), {'candidate', 'full', 'binaries'})
        for name, job in release['jobs'].items():
            if name != 'publish':
                self.assertNotEqual(job.get('permissions', {}).get('contents'), 'write')
        steps = release['jobs']['publish']['steps']
        commands = [step.get('run', '') for step in steps]
        verify = next(i for i, text in enumerate(commands) if 'gh attestation verify' in text)
        publish = next(i for i, text in enumerate(commands) if 'git push' in text)
        self.assertLess(verify, publish)
        self.assertIn('--notes-file build/release-notes.md', commands[publish])
        self.assertNotIn('--generate-notes', commands[publish])
        self.assertIn('--source-digest', commands[verify])
        self.assertIn('--signer-workflow', commands[verify])
        self.assertEqual(release['name'], 'CLI release gate')
        self.assertEqual(release['concurrency']['group'], 'cli-release')

    def test_static_checks_run_in_both_pr_and_full(self):
        jobs = workflow('cli-checks.yml')['jobs']
        for name in ('quality', 'codeql'):
            self.assertNotIn('if', jobs[name])
        quality = workflow('quality.yml')['jobs']
        self.assertIn('clang-tidy', quality)
        self.assertIn('check_static.py', str(quality))

    def test_full_timings_exclude_parent_release_jobs(self):
        for name in ('cli-pr.yml', 'cli-full.yml'):
            timing_steps = workflow(name)['jobs']['timings']['steps']
            self.assertTrue(any('--scope cli' in step.get('run', '') for step in timing_steps))


if __name__ == '__main__':
    unittest.main()
