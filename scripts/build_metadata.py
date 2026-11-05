#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Record actual build inputs and binary imports without requiring hosted CI."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from binary_linkage import check_static_core, core_library
from ci_support import cache, digest, pin, read, require, write


def source_identity(source):
    """Never attribute an export to the enclosing workspace's Git repository."""
    if not source:
        return {'commit': None, 'dirty': None}
    source = Path(source).resolve()

    def git(*args):
        try:
            result = subprocess.run(['git', '-C', str(source), *args], capture_output=True,
                                    text=True, encoding='utf-8', check=False)
        except FileNotFoundError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    root = git('rev-parse', '--show-toplevel')
    if not root or Path(root).resolve() != source:
        return {'commit': None, 'dirty': None}
    commit = git('rev-parse', 'HEAD')
    status = git('status', '--porcelain', '--untracked-files=all')
    require(commit and re.fullmatch('[0-9a-f]{40}', commit) and status is not None,
            'Cannot inspect source identity: ' + str(source))
    return {'commit': commit, 'dirty': bool(status)}


def header_identity(includes):
    """Hash selected public headers, including generated configuration headers.

    Relative names and content hashes give installed packages a relocatable
    content identity, without inventing an upstream Git revision.
    """
    files = {}
    for entry in includes.split(';'):
        if not entry:
            continue
        root = Path(entry)
        require(root.is_dir(), 'Missing public include directory: ' + entry)
        for path in sorted(root.rglob('*')):
            if path.is_file() and path.suffix in ('.h', '.hpp', '.hxx', '.inc'):
                name = path.relative_to(root).as_posix()
                value = digest(path)
                require(name not in files or files[name] == value, 'Conflicting public header: ' + name)
                files[name] = value
    require(files, 'No public headers found')
    payload = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'sha256': hashlib.sha256(payload).hexdigest(), 'files': len(files)}


def json_version(includes):
    for entry in includes.split(';'):
        for relative in ('nlohmann/detail/abi_macros.hpp', 'nlohmann/json.hpp'):
            path = Path(entry) / relative
            if path.is_file():
                text = path.read_text(encoding='utf-8')
                parts = [re.search(r'^\s*#\s*define\s+NLOHMANN_JSON_VERSION_' + part + r'\s+(\d+)',
                                   text, re.MULTILINE) for part in ('MAJOR', 'MINOR', 'PATCH')]
                if all(parts):
                    return '.'.join(part[1] for part in parts)
    raise ValueError('Cannot determine selected nlohmann/json header version')


def startup(executable, version):
    environment = os.environ.copy()
    for name in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'):
        environment.pop(name, None)
    result = subprocess.run([str(executable), '--version'], cwd=executable.parent,
                            env=environment, capture_output=True, text=True, timeout=30, check=False)
    require(result.returncode == 0 and result.stdout.strip() == 'OpenTLV CLI ' + version and
            not result.stderr, 'Executable startup/version verification failed')
    return {'status': 'passed', 'command': ['--version'], 'exit_code': result.returncode}


def collect(build, configuration, verify_startup=False):
    inputs = read(build / f'cli-build-inputs-{configuration}.json')
    require(inputs['configuration'] == configuration, 'Wrong build configuration')
    require(inputs['core_type'] == 'STATIC_LIBRARY', 'Expected a static Core target')
    executable = Path(inputs['executable'])
    imports = check_static_core(executable)
    version = (build / 'cli-version.txt').read_text(encoding='utf-8').strip()
    core = source_identity(inputs['core_source']) if inputs['core_imported'] not in ('TRUE', '1') else {
        'commit': None, 'dirty': None}
    core.update({'selection': 'package' if inputs['core_imported'] in ('TRUE', '1') else 'source',
                 'requested_commit': pin('Core'), 'library_sha256': digest(Path(inputs['core_library'])),
                 'headers': header_identity(inputs['core_includes'])})
    json_imported = inputs.get('json_imported') in ('TRUE', '1')
    third_party = source_identity('' if json_imported else inputs['json_source'])
    third_party.update({'selection': 'package' if json_imported else 'source',
                        'requested_commit': pin('Json'), 'version': json_version(inputs['json_includes']),
                        'headers': header_identity(inputs['json_includes'])})
    selected = cache(build)
    # Keep reconstruction inputs, not the entire cache (which may hold credentials).
    settings = {key: value for key, value in selected.items() if
                key.startswith(('OPENTLV_', 'JSON_', 'FETCHCONTENT_SOURCE_DIR_')) or
                re.fullmatch(r'CMAKE_(?:C|CXX|EXE_LINKER|STATIC_LINKER)_FLAGS(?:_[A-Z]+)?', key) or
                key in ('CMAKE_BUILD_TYPE', 'CMAKE_PREFIX_PATH', 'CMAKE_INTERPROCEDURAL_OPTIMIZATION',
                        'OpenTLV_DIR', 'opentlv_core_DIR', 'nlohmann_json_DIR',
                        'FETCHCONTENT_TRY_FIND_PACKAGE_MODE', 'BUILD_SHARED_LIBS')}
    result = {'schema': 1, 'cli': source_identity(inputs['source']) | {'version': version},
              'core': core, 'json': third_party, 'configuration': configuration,
              'toolchain': {key: value for key, value in inputs.items() if key.startswith('CMAKE_')},
              'settings': settings, 'sanitizer': inputs['OPENTLV_CLI_SANITIZER'],
              'binary': {'filename': executable.name, 'sha256': digest(executable),
                         'core_linkage': 'static', 'runtime_imports': imports,
                         'startup': {'status': 'not-run'}}}
    toolchain_file = inputs.get('CMAKE_TOOLCHAIN_FILE')
    if toolchain_file:
        result['toolchain_file_sha256'] = digest(Path(toolchain_file))
    if verify_startup:
        require(inputs['CMAKE_CROSSCOMPILING'] not in ('TRUE', '1'),
                'Startup verification requires a native target environment')
        result['binary']['startup'] = startup(executable, version)
    return result


def validate_release(metadata, record):
    """Release evidence must identify the tested executable and actual toolchain."""
    require(metadata.get('schema') == 1 and metadata.get('configuration') == record['configuration'],
            'Missing/wrong build provenance')
    cli = metadata.get('cli', {})
    require(cli.get('commit') == record['commit'] and cli.get('version') == record['version'] and
            cli.get('dirty') is False, 'Wrong/dirty CLI provenance')
    core = metadata.get('core', {})
    require(core.get('requested_commit') == record['core']['commit'] and
            core.get('commit') in (None, record['core']['commit']) and core.get('dirty') in (None, False),
            'Wrong/dirty Core provenance')
    third_party = metadata.get('json', {})
    require(third_party.get('commit') == record['json_commit'] and third_party.get('dirty') is False,
            'Wrong/dirty JSON provenance')
    for dependency in (core, third_party):
        require(re.fullmatch('[0-9a-f]{64}', dependency.get('headers', {}).get('sha256', '')) and
                dependency['headers'].get('files', 0) > 0, 'Missing dependency header identity')
    require(re.fullmatch('[0-9a-f]{64}', core.get('library_sha256', '')) and third_party.get('version'),
            'Missing dependency library/version identity')
    toolchain = metadata.get('toolchain', {})
    system = {'windows': 'Windows', 'linux': 'Linux', 'macos': 'Darwin'}.get(record['id'].split('-')[0])
    require(all(toolchain.get('CMAKE_' + language + '_COMPILER_' + field)
                for language in ('C', 'CXX') for field in ('ID', 'VERSION')) and
            system is not None and toolchain.get('CMAKE_SYSTEM_NAME') == system and
            toolchain.get('CMAKE_SIZEOF_VOID_P') == '8', 'Incomplete/wrong target toolchain provenance')
    binary = metadata.get('binary', {})
    imports = binary.get('runtime_imports')
    require(binary.get('core_linkage') == 'static' and isinstance(imports, list) and imports and
            all(isinstance(name, str) and name and not core_library(name) for name in imports) and
            binary.get('startup', {}).get('status') == 'passed' and
            re.fullmatch('[0-9a-f]{64}', binary.get('sha256', '')), 'Incomplete binary verification')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--configuration', default='Release')
    parser.add_argument('--verify-startup', action='store_true')
    args = parser.parse_args()
    build = args.build.resolve()
    output = build / f'build-info-{args.configuration}.json'
    # A failed refresh must not leave stale successful evidence behind.
    output.unlink(missing_ok=True)
    write(output, collect(build, args.configuration, args.verify_startup))
    print('Build provenance: ' + str(output))


if __name__ == '__main__':
    main()
