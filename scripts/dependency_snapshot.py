# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Submit dependencies observed in a successful Main build to GitHub."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re

from ci_support import ROOT, identity, pin, read, require, run, same_identity, write


def package_url(name):
    text = (ROOT / 'cmake' / (name + '.cmake')).read_text(encoding='utf-8')
    repos = re.findall(r'GIT_REPOSITORY\s+https://github.com/([\w.-]+/[\w.-]+)\.git\s', text)
    require(len(repos) == 1, 'Expected one GitHub dependency origin in ' + name + '.cmake')
    return 'pkg:github/' + repos[0].lower() + '@' + pin(name)


def resolved_dependencies(build, configuration, core, json_source):
    """Check the actual target edges and source provenance before assigning pins.

    Core's C++ facade and native library are one package, not a false transitive
    dependency. The selected Core/JSON currently have no third-party target
    dependencies. Fail on new edges rather than silently publish a partial graph.
    """
    lines = (build / f'cli-dependencies-{configuration}.txt').read_text(encoding='utf-8').splitlines()
    targets = ('otlv', 'OpenTLV::tlv++', 'OpenTLV::tlv', 'nlohmann_json::nlohmann_json')
    require(len(lines) == 20, 'Malformed CMake dependency observations')
    observations = {lines[i]: lines[i + 1:i + 5] for i in range(0, 20, 5)}
    require(set(observations) == set(targets), 'Missing CMake dependency targets')
    owners = dict(zip(targets, ('CLI', 'Core', 'Core', 'Json')))
    aliases = {value[0]: owners[target] for target, value in observations.items()}
    aliases.update(owners)
    edges = {name: set() for name in ('CLI', 'Core', 'Json')}
    for target, (_, source, direct, interface) in observations.items():
        if target == 'nlohmann_json::nlohmann_json':
            require(Path(source).resolve().is_relative_to(json_source.resolve()),
                    'JSON target does not originate in the verified checkout')
        for link in (direct + ';' + interface).split(';'):
            if not link:
                continue
            require(link in aliases, 'Unresolved dependency edge ' + target + ' -> ' + link +
                    '; extend dependency discovery before submitting a partial graph')
            if owners[target] != aliases[link]:
                edges[owners[target]].add(aliases[link])
    require(edges['CLI'] == {'Core', 'Json'}, 'Unexpected CLI direct dependency selection')
    require(not edges['Core'] and not edges['Json'], 'Unexpected external Core/JSON dependency relationships')
    require(core.get('commit') == pin('Core') and core.get('mode') in
            ('pinned-git', 'verified-source', 'verified-binary'), 'Untraceable Core dependency')
    if core['mode'] != 'pinned-git':
        require(core.get('verified') is True, 'Core artifact was not authenticated')
    return {name: {'package_url': package_url(name), 'relationship': 'direct',
                   'scope': 'runtime', 'dependencies': []} for name in ('Core', 'Json')}


def snapshot(evidence):
    same_identity(evidence)
    require(evidence.get('schema') == 1 and evidence.get('configuration') == 'Release' and
            evidence.get('core_linkage') == 'static' and not evidence.get('sanitizer'),
            'Expected successful Main Release build evidence')
    reports = evidence.get('reports')
    require(isinstance(reports, dict) and isinstance(reports.get('ctest'), dict), 'Missing Main test evidence')
    tests = reports['ctest']
    expected = sorted(('core_c_smoke', 'core_cxx_smoke', 'cli_version', 'cli_static_core'))
    require(tests.get('names') == expected and tests.get('tests') == 4 and tests.get('passed') == 4 and
            tests.get('failed') == 0 and tests.get('skipped') == 0, 'Main smoke verification incomplete')
    core = evidence.get('core', {})
    require(isinstance(core, dict), 'Missing Core dependency evidence')
    require(core.get('commit') == pin('Core') and evidence.get('json_commit') == pin('Json'),
            'Dependency evidence differs from CMake pins')
    require(core.get('mode') == 'pinned-git' or
            (core.get('mode') in ('verified-source', 'verified-binary') and core.get('verified') is True),
            'Local/unverified Core selection cannot be submitted')
    expected_dependencies = {name: {'package_url': package_url(name), 'relationship': 'direct',
                                    'scope': 'runtime', 'dependencies': []} for name in ('Core', 'Json')}
    require(evidence.get('dependencies') == expected_dependencies, 'Missing or inconsistent resolved dependencies')
    selected = identity()
    return {'version': 0, 'sha': selected['commit'], 'ref': os.environ['GITHUB_REF'],
            'job': {'id': selected['run_id'] + '-' + selected['run_attempt'],
                    'correlator': 'cli-main-dependencies',
                    'html_url': 'https://github.com/' + selected['repository'] + '/actions/runs/' + selected['run_id']},
            'detector': {'name': 'opentlv-cli-cmake', 'version': '1.0.0',
                         'url': 'https://github.com/OpenTLV/opentlv-cli'},
            'scanned': datetime.now(timezone.utc).isoformat(),
            'manifests': {'CMakeLists.txt': {'name': 'CMakeLists.txt',
                                           'file': {'source_location': 'CMakeLists.txt'},
                                           'resolved': evidence['dependencies']}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--submit', action='store_true')
    args = parser.parse_args()
    require(run('git', 'rev-parse', 'HEAD', capture=True) == identity()['commit'], 'Wrong dependency checkout')
    if args.submit:
        require(os.environ.get('GITHUB_EVENT_NAME') == 'push' and
                os.environ.get('GITHUB_REF') == 'refs/heads/main' and
                os.environ.get('GITHUB_REPOSITORY') == 'OpenTLV/opentlv-cli',
                'Dependency submission is restricted to canonical Main pushes')
    write(args.output, snapshot(read(args.evidence)))
    if args.submit:
        response = run('gh', 'api', '--method', 'POST',
                       'repos/' + identity()['repository'] + '/dependency-graph/snapshots',
                       '-H', 'Accept: application/vnd.github+json',
                       '-H', 'X-GitHub-Api-Version: 2022-11-28', '--input', args.output, capture=True)
        args.output.with_suffix('.response.json').write_text(response + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
