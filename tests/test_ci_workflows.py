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

    def test_core_linkage_is_not_a_matrix_axis(self):
        checks = workflow('cli-checks.yml')['jobs']
        release = workflow('release.yml')['jobs']
        for name, job in (('build', checks['build']), ('dependencies', checks['dependencies']),
                          ('binaries', release['binaries'])):
            with self.subTest(job=name):
                self.assertNotIn('shared', str(job['strategy']['matrix']))
                self.assertNotIn('--shared', str(job['steps']))
        # Full builds static Core on each supported platform; release packaging reuses all three builds.
        matrix = str(checks['build']['strategy']['matrix']['include'])
        for runner in ('ubuntu-26.04', 'windows-2025', 'macos-26'):
            self.assertIn(runner, matrix)
        self.assertEqual(release['binaries']['strategy']['matrix']['os'], ['ubuntu-26.04', 'windows-2025', 'macos-26'])

    def test_cxx_jobs_use_the_supported_stable_compilers(self):
        checks = workflow('cli-checks.yml')['jobs']
        release = workflow('release.yml')['jobs']
        # PR: Linux Clang Debug. Full: GCC, MSVC and AppleClang Release, one entry each.
        build = checks['build']
        self.assertEqual(build['env'], {'CC': '${{ matrix.cc }}', 'CXX': '${{ matrix.cxx }}'})
        matrix = build['strategy']['matrix']['include']
        full, pr = matrix.split("'")[1], matrix.split("'")[3]
        for entry in ('"os":"ubuntu-26.04","configuration":"Release","cc":"gcc-15","cxx":"g++-15"',
                      '"os":"windows-2025","configuration":"Release","cc":"cl","cxx":"cl"',
                      '"os":"macos-26","configuration":"Release","cc":"clang","cxx":"clang++"'):
            self.assertIn(entry, full)
        self.assertEqual(pr, '[{"os":"ubuntu-26.04","configuration":"Debug",'
                             '"cc":"clang-22","cxx":"clang++-22"}]')
        # Release signs Full's tested packages without another compiler/build.
        self.assertNotIn('env', release['binaries'])
        self.assertNotIn('cli_build.py', str(release['binaries']))
        self.assertIn('cli-tested-package-', str(release['binaries']))
        self.assertIn('--package build/artifacts', str(build['steps']))
        self.assertNotIn('!= macOS', str(build['steps']))
        self.assertNotIn("runner.os != 'macOS'", str(build['steps']))
        for job in (checks['dependencies'],):
            self.assertIn("'gcc-15'", job['env']['CC'])
            self.assertIn("'g++-15'", job['env']['CXX'])
            self.assertIn("'cl'", job['env']['CC'])
        main_env = workflow('cli-main.yml')['jobs']['smoke']['env']
        self.assertEqual((main_env['CC'], main_env['CXX']), ('gcc-15', 'g++-15'))
        # Clang-based analysis follows the PR compiler; no stale toolchain remains.
        for name in ('cli-checks.yml', 'quality.yml', 'cli-codeql.yml'):
            text = (ROOT / '.github/workflows' / name).read_text(encoding='utf-8')
            self.assertIn('clang-22', text)
            self.assertNotRegex(text, r'clang(\+\+|-tidy)?-(1[0-9]|2[01])\b')
        self.assertEqual(checks['sanitizer']['strategy']['matrix']['include'], [
            {'os': 'ubuntu-26.04', 'cc': 'clang-22', 'cxx': 'clang++-22'},
            {'os': 'windows-2025', 'cc': 'cl', 'cxx': 'cl'}])
        for name in ('build', 'dependencies', 'sanitizer'):
            self.assertNotIn('24.04', str(checks[name]))

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

    def test_dependency_submission_is_main_only_with_isolated_write_permission(self):
        main = workflow('cli-main.yml')
        self.assertEqual(main['permissions'], {'contents': 'read'})
        job = main['jobs']['dependencies']
        self.assertEqual(job['needs'], 'smoke')
        self.assertEqual(job['permissions'], {'contents': 'write'})
        self.assertIn('dependencies', main['jobs']['gate']['needs'])
        self.assertIn('github.run_attempt', str(job['steps']))
        for filename in ('cli-pr.yml', 'cli-full.yml', 'cli-checks.yml', 'release.yml'):
            self.assertNotIn('dependency_snapshot.py', str(workflow(filename)))
        checkout = job['steps'][0]
        self.assertIs(checkout['with']['persist-credentials'], False)

    def test_cache_contains_downloads_only_without_restore_prefix(self):
        for filename in ('cli-main.yml', 'cli-checks.yml'):
            for job in workflow(filename)['jobs'].values():
                for step in job.get('steps', []):
                    if step.get('uses') == 'actions/cache@v4':
                        self.assertEqual(step['with']['path'], '.cache/core-downloads')
                        self.assertNotIn('restore-keys', step['with'])
                        self.assertIn("hashFiles('cmake/core-artifact.json')", step['with']['key'])


if __name__ == '__main__':
    unittest.main()
