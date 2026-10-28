# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""PR/Main/Full gates and exact-commit release assembly, following Core #637."""

import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from ci_support import ROOT, digest, identity, read, require, run, same_identity, write
from release import QUERY_EXCLUSIONS, TESTS, aggregate, prepare
from verified_core import authenticated_release, lock, safe_name

JOBS = {'build', 'dependencies', 'quality', 'sanitizer', 'codeql'}
PR = {'build', 'quality', 'codeql'}
IDS = {f'{system}-x64-{link}' for system in ('linux', 'windows') for link in ('static', 'shared')}


def check_results(results, tier):
    expected = {'smoke'} if tier == 'main' else JOBS
    required = expected if tier in ('main', 'full') else PR
    require(isinstance(results, dict) and set(results) == expected, 'Missing/unexpected CI jobs')
    for name, item in results.items():
        require(isinstance(item, dict) and item.get('result') == ('success' if name in required else 'skipped'),
                'Required CI result missing/failed/cancelled/skipped: ' + name)


def configuration(tier):
    names = ['cli-' + tier + '.yml']
    if tier != 'main':
        names += ['cli-checks.yml', 'quality.yml', 'cli-codeql.yml']
    if os.environ.get('RELEASE_TAG'):
        names.append('release.yml')
    helpers = ['CMakeLists.txt', 'src/CMakeLists.txt', 'tests/CMakeLists.txt', 'cmake/Core.cmake',
               'cmake/Json.cmake', 'cmake/core-artifact.json', 'scripts/cli_build.py',
               'scripts/verified_core.py', 'scripts/cli_ci.py', 'scripts/ci_support.py',
               'scripts/check_static.py', 'scripts/check_tidy.py', 'cmake/Runtime.cmake',
               'cmake/Version.cmake', 'tests/check_core_dependency.py']
    return {'release_tag': os.environ.get('RELEASE_TAG', ''),
            'workflows': {name: {'sha256': digest(ROOT / '.github/workflows' / name),
                                 'definition': (ROOT / '.github/workflows' / name).read_text(encoding='utf-8')}
                          for name in names},
            'sources': {name: digest(ROOT / name) for name in helpers}}


def gate(tier, results):
    check_results(results, tier)
    require(run('git', 'rev-parse', 'HEAD', capture=True) == identity()['commit'], 'Wrong gate checkout')
    return {'schema': 2, 'tier': tier, **identity(), 'configuration': configuration(tier),
            'checks': {key: value['result'] for key, value in results.items()}}


def closed_changelog(text, tag):
    require('unreleased' not in text.lower(), 'Close the changelog before requesting release')
    sections = re.split(r'^## ', text, flags=re.MULTILINE)
    require(len(sections) > 1, 'Missing release changelog')
    heading, _, body = sections[1].partition('\n')
    require(tag.startswith('v'), 'Release tag must have a v prefix')
    match = re.fullmatch(r'\[' + re.escape(tag[1:]) + r'\] - (\d{4}-\d{2}-\d{2})', heading.strip())
    require(match is not None, 'First release heading must match the release tag without its v prefix')
    date.fromisoformat(match[1])
    require(re.search(r'^- \S', body, re.MULTILINE), 'Empty release changelog')
    return body.strip() + '\n'


def preflight(tag):
    require(os.environ.get('GITHUB_REF') == 'refs/heads/main' and
            os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'Release must be dispatched from main')
    selected = identity()
    require(selected['repository'] == 'OpenTLV/opentlv-cli', 'Wrong publishing repository')
    request = prepare(selected['commit'], tag)
    require(request['workflow_sha'] == selected['commit'], 'Release must use the dispatch SHA')
    require(not run('git', 'status', '--porcelain', capture=True), 'Dirty release checkout')
    require(not run('git', 'ls-remote', '--tags', 'origin', 'refs/tags/' + tag, capture=True), 'Tag already exists')
    remote_tags = run('git', 'ls-remote', '--tags', 'origin', 'refs/tags/v*', capture=True)
    require(not any(line.split()[0] == selected['commit'] for line in remote_tags.splitlines()),
            'Release commit already has a remote version tag')
    notes = closed_changelog((ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'), tag)
    request['core_lock'] = lock(True)
    (ROOT / 'build').mkdir(exist_ok=True)
    (ROOT / 'build/release-notes.md').write_text(notes, encoding='utf-8')
    work = Path(tempfile.mkdtemp(prefix='core-preflight-', dir=ROOT / 'build'))
    _, _, _, request['core_release'] = authenticated_release(work / 'assets', request['core_lock'])
    request['repository'] = selected['repository']
    return request


def check_full(quality):
    same_identity(quality)
    require(quality.get('schema') == 2 and quality.get('tier') == 'full', 'Full CI evidence required')
    check_results({key: {'result': value} for key, value in quality.get('checks', {}).items()}, 'full')
    require(quality.get('configuration') == configuration('full'), 'Wrong tested Full configuration')


def assemble(request, quality, evidence, destination):
    require(request == preflight(request['tag']), 'Candidate lock changed')
    check_full(quality)
    # Preserve the existing dependency scenarios and portal result contract.
    result = aggregate(request, evidence)
    records = []
    seen = set()
    destination.mkdir(parents=True, exist_ok=False)
    for path in sorted(evidence.rglob('*.json')):
        if path.name not in {identifier + '.json' for identifier in IDS}:
            continue
        record = read(path)
        same_identity(record)
        identifier = record.get('id')
        require(identifier in IDS and identifier not in seen, 'Duplicate/unexpected CLI package')
        require(path.name == identifier + '.json', 'CLI package record filename mismatch')
        seen.add(identifier)
        require(record.get('schema') == 1 and record.get('version') == request['version'] and
                record.get('configuration') == 'Release' and
                record.get('package_cases') == 154 and not record.get('sanitizer'), 'Invalid package evidence')
        reports = record.get('reports', {})
        tests = reports.get('ctest', {})
        require(tests.get('names') == sorted(TESTS) and tests.get('tests') == len(TESTS) and
                tests.get('passed') == len(TESTS) and
                tests.get('failed') == 0 and tests.get('skipped') == 0 and
                reports.get('baseline_cases') == 154 and reports.get('query', {}).get('checks') == 338 and
                reports['query'].get('exclusions') == QUERY_EXCLUSIONS, 'Incomplete packaged build test evidence')
        require(record.get('shared') == ('ON' if identifier.endswith('-shared') else 'OFF') and
                record.get('compiler', {}).get('SIZEOF_DATA_PTR') == '8' and
                record['compiler'].get('COMPILER_ID') == ('MSVC' if identifier.startswith('windows-') else 'GNU'),
                'Wrong package platform/linkage/compiler')
        dependency = record.get('core', {})
        require(dependency.get('verified') is True and dependency.get('commit') == request['core_sha'] and
                dependency.get('release_tag') == request['core_lock']['release_tag'] and
                dependency.get('mode') in ('verified-binary', 'verified-source'), 'Unverified release dependency')
        require(all(dependency.get(key) == value for key, value in request['core_release'].items()),
                'Core release assets changed since preflight')
        require(record.get('json_commit') == request['json_sha'], 'Wrong JSON dependency')
        filename = safe_name(record['filename'])
        extension = '.zip' if identifier.startswith('windows-') else '.tar.gz'
        require(filename == f"OpenTLV-CLI-{request['version']}-{identifier}{extension}", 'Wrong CLI archive name')
        require(digest(path.parent / filename) == record['sha256'], 'CLI package checksum mismatch')
        shutil.copy2(path.parent / filename, destination / filename)
        shutil.copy2(path, destination / path.name)
        records.append(record)
    require(seen == IDS, 'Missing approved CLI packages')
    result.update({'schema': 2, 'jobs': {'validation': 'success', 'quality': 'success'},
                   'full': quality, 'artifacts': records})
    write(destination / 'release-manifest.json', result)
    # Portal continues reading result.json; only successful publication triggers it.
    write(destination.parent / 'result.json', result)
    files = sorted(destination.iterdir())
    (destination / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in files), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('gate')
    check.add_argument('--tier', choices=('pr', 'main', 'full'), required=True)
    check.add_argument('--output', type=Path, required=True)
    prep = sub.add_parser('preflight')
    prep.add_argument('--output', type=Path, required=True)
    prep.add_argument('--locked', type=Path)
    publish = sub.add_parser('assemble')
    publish.add_argument('--request', type=Path, required=True)
    publish.add_argument('--quality', type=Path, required=True)
    publish.add_argument('--evidence', type=Path, required=True)
    publish.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'gate':
        write(args.output, gate(args.tier, json.loads(os.environ['CHECK_RESULTS'])))
    elif args.command == 'preflight':
        request = preflight(os.environ['RELEASE_TAG'])
        if args.locked:
            require(read(args.locked) == request, 'Locked candidate changed')
        write(args.output, request)
    else:
        assemble(read(args.request), read(args.quality), args.evidence, args.output)


if __name__ == '__main__':
    main()
