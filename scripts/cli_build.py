# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Build/test CLI behavior and package the tested executable through public Core targets."""

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from binary_linkage import check_static_core
from ci_support import ROOT, cache, compiler, digest, identity, pin, read, require, run, write
from release import QUERY_EXCLUSIONS, ctest_results
from verified_core import extract, resolve

# Main's smoke tier: Core linkage, both public targets and the version contract.
SMOKE = ('core_c_smoke', 'core_cxx_smoke', 'cli_version', 'cli_static_core')


def platform_id():
    system = {'Windows': 'windows', 'Darwin': 'macos'}.get(platform.system(), 'linux')
    machine = platform.machine().lower()
    architecture = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64'}.get(machine, machine)
    return system, architecture


def validate_reports(build, configuration):
    tests = ctest_results(build / 'ctest.xml')
    baseline = read(build / f'tests/Integration_cli_baseline-{configuration}/baseline-report.json')
    query = read(build / f'tests/query-cli-conformance-{configuration}/query-report.json')
    require(len(baseline['observations']) == 154 and baseline['failures'] == [], 'CLI baseline incomplete')
    require(query['checks'] == 338 and query['exclusions'] == QUERY_EXCLUSIONS, 'CLI Query evidence incomplete')
    return {'ctest': tests, 'baseline_cases': 154, 'query': query}


def core_source(build):
    # FetchContent's lowercase source variable is not a CMake cache entry.
    selection = (build / 'tests/core-selection.txt').read_text(encoding='utf-8').splitlines()
    require(len(selection) >= 5 and selection[0] == 'source' and selection[1], 'Expected a Core source selection')
    source = Path(selection[1]).resolve()
    require(selection[4] in ('FALSE', '0') and
            all(Path(path).resolve().is_relative_to(source) for path in selection[2:4]),
            'Core public targets must originate in the selected source')
    return source


def built_executable(build, configuration):
    """Return the tested executable after proving Core was linked statically into it."""
    paths = (build / f'cli-package-paths-{configuration}.txt').read_text(encoding='utf-8').splitlines()
    require(len(paths) == 3 and paths[2] == 'STATIC_LIBRARY', 'The CLI requires a static OpenTLV::tlv')
    executable = Path(paths[0])
    check_static_core(executable)
    return executable


def package(build, output, record):
    """Stage only the statically linked CLI; test after archive relocation."""
    executable = built_executable(build, record['configuration'])
    output.mkdir(parents=True, exist_ok=False)
    require(platform_id() in (('linux', 'x64'), ('windows', 'x64')),
            'Approved packages require a Linux or Windows x64 host')
    identifier = record['id']
    name = f"OpenTLV-CLI-{record['version']}-{identifier}"
    work = Path(tempfile.mkdtemp(prefix='package-check-', dir=build))
    stage = work / name
    (stage / 'bin').mkdir(parents=True, exist_ok=False)
    run('cmake', '--install', build, '--config', record['configuration'], '--prefix', stage,
        '--component', 'cli-runtime')
    # Static Core: the package holds the executable alone, never a Core runtime.
    require(sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*')) ==
            ['bin', 'bin/' + executable.name], 'CLI install must contain only the executable')
    licenses = stage / 'licenses'
    licenses.mkdir()
    shutil.copy2(ROOT / 'LICENSE', licenses / 'OpenTLV-CLI.txt')
    selected = cache(build)
    if selected.get('OPENTLV_CLI_CORE_PACKAGE'):
        prefix = Path(selected['OPENTLV_CLI_CORE_PACKAGE']).parents[2]
        core_license = prefix / 'share/doc/OpenTLV/LICENSE'
    else:
        core_license = core_source(build) / 'LICENSE'
    shutil.copy2(core_license, licenses / 'OpenTLV.txt')
    json_source = Path(selected['nlohmann_json_SOURCE_DIR'])
    shutil.copy2(json_source / 'LICENSE.MIT', licenses / 'nlohmann-json.txt')
    write(stage / 'build-info.json', record)
    archive_format = 'zip' if platform.system() == 'Windows' else 'gztar'
    archive = Path(shutil.make_archive(str(output / name), archive_format, stage.parent, stage.name))
    relocated = work / 'relocated'
    extract(archive, relocated)
    cli = relocated / name / 'bin' / executable.name
    check_static_core(cli)
    # Remove build-tree runtime search paths from the environment. The relocated
    # executable must start without them, from a different working directory.
    environment = os.environ.copy()
    environment.pop('LD_LIBRARY_PATH', None)
    environment.pop('DYLD_LIBRARY_PATH', None)
    result = subprocess.run([str(cli), '--version'], cwd=relocated, env=environment,
                            capture_output=True, text=True, check=True)
    require(result.stdout.strip() == 'OpenTLV CLI ' + record['version'] and not result.stderr,
            'Relocated executable version mismatch')
    # All 154 observable CLI cases, not merely a --help/--version launch.
    run(sys.executable, '-B', ROOT / 'tests/check_cli_baseline.py', '--cli', cli,
        '--version', record['version'], '--report', output / 'package-baseline.json', env=environment)
    report = read(output / 'package-baseline.json')
    require(len(report['observations']) == 154 and not report['failures'], 'Packaged CLI behavior mismatch')
    write(output / (identifier + '.json'), record | {'filename': archive.name, 'sha256': digest(archive),
                                                   'package_cases': 154})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--configuration', choices=('Debug', 'Release'), default='Release')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--release-tag', default='')
    parser.add_argument('--package', type=Path)
    parser.add_argument('--core-source', type=Path, help='Local unverified development override')
    parser.add_argument('--json-source', type=Path, help='Local pinned JSON checkout for offline validation')
    args = parser.parse_args()
    build = args.build.resolve()
    require(not (build / 'CMakeCache.txt').exists(), 'Use a fresh CI build directory')
    require(not args.release_tag or not args.smoke, 'Release cannot use smoke-only tests')
    require(not args.release_tag or not (args.core_source or args.json_source), 'Release forbids local overrides')
    if args.core_source:
        source = args.core_source.resolve()
        options = [f'-DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE={source.as_posix()}']
        dependency = {'mode': 'local-source', 'verified': False,
                      'commit': run('git', '-C', source, 'rev-parse', 'HEAD', capture=True)}
    else:
        options, dependency = resolve(build / 'core', args.configuration,
                                      required=bool(args.release_tag), source_only=args.sanitize)
    if args.json_source:
        options.append(f'-DFETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON={args.json_source.resolve().as_posix()}')
    common = ['-G', 'Ninja', f'-DCMAKE_BUILD_TYPE={args.configuration}',
              '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
              '-DOPENTLV_BUILD_TESTS=OFF', '-DOPENTLV_BUILD_EXAMPLES=OFF',
              '-DOPENTLV_BUILD_BENCHMARKS=OFF', '-DOPENTLV_BUILD_PROPERTY_TESTS=OFF',
              '-DOPENTLV_BUILD_CXX=ON',
              '-DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER', '-DOPENTLV_CLI_BUILD_TESTS=ON']
    if args.release_tag:
        common += [f'-DOPENTLV_CLI_CANDIDATE_VERSION={args.release_tag[1:]}',
                   f"-DOPENTLV_CLI_CANDIDATE_SHA={os.environ['GITHUB_SHA']}"]
    if args.sanitize:
        flags = '-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all'
        common += [f'-DCMAKE_C_FLAGS={flags}', f'-DCMAKE_CXX_FLAGS={flags}',
                   '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
    run('cmake', '-S', ROOT, '-B', build, *common, *options)
    selected = cache(build)
    if dependency['mode'] == 'pinned-git':
        source = core_source(build)
        require(run('git', '-C', source, 'rev-parse', 'HEAD', capture=True) == pin('Core'), 'Wrong Core checkout')
        require(not run('git', '-C', source, 'status', '--porcelain', capture=True), 'Dirty Core checkout')
    json_source = Path(selected['nlohmann_json_SOURCE_DIR'])
    require(run('git', '-C', json_source, 'rev-parse', 'HEAD', capture=True) == pin('Json'), 'Wrong JSON revision')
    run('cmake', '--build', build, '--parallel', '2')
    selection = ['-R', '^(' + '|'.join(SMOKE) + ')$'] if args.smoke else []
    run('ctest', '--test-dir', build, '--output-on-failure', '--no-tests=error',
        '--output-junit', build / 'ctest.xml', *selection)
    reports = ({'ctest': ctest_results(build / 'ctest.xml', set(SMOKE))}
               if args.smoke else validate_reports(build, args.configuration))
    built_executable(build, args.configuration)
    system, architecture = platform_id()
    record = {'schema': 1, **identity(), 'id': f'{system}-{architecture}-static',
              'version': (build / 'cli-version.txt').read_text().strip(), 'core_linkage': 'static',
              'configuration': args.configuration, 'compiler': compiler(build), 'core': dependency,
              'architecture': platform.machine(), 'libc': list(platform.libc_ver()),
              'msvc_runtime': selected.get('CMAKE_MSVC_RUNTIME_LIBRARY') if system == 'windows' else None,
              'runner_image': {'os': os.environ.get('ImageOS'), 'version': os.environ.get('ImageVersion')},
              'json_commit': pin('Json'), 'sanitizer': args.sanitize, 'reports': reports}
    write(build / 'build-evidence.json', record)
    if args.package:
        require(not args.smoke and args.configuration == 'Release' and not args.sanitize,
                'Package requires a fully tested Release configuration')
        package(build, args.package.resolve(), record)


if __name__ == '__main__':
    main()
