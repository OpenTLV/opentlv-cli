# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""CLI archive contract shared by native packaging and publication verification."""

import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import tarfile
import tempfile
import zipfile

from binary_linkage import check_static_core
from ci_support import digest, read, require
from verified_core import extract

# Match the existing Full runners, not a compiler compatibility matrix.
TARGETS = {
    'linux-x64-static': ('Linux', 'x64', 'GNU', '.tar.gz'),
    'windows-x64-static': ('Windows', 'x64', 'MSVC', '.zip'),
    'macos-arm64-static': ('Darwin', 'arm64', 'AppleClang', '.tar.gz'),
}
SMOKE_CASES = ['version', 'help', 'encode-file', 'dump-file', 'invalid-input']
PACKAGE_FIELDS = {'filename', 'sha256', 'package_verification'}


def native_id():
    system = {'Linux': 'linux', 'Windows': 'windows', 'Darwin': 'macos'}.get(platform.system())
    machine = platform.machine().lower()
    architecture = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64'}.get(machine, machine)
    return f'{system}-{architecture}-static'


def archive_name(record):
    require(record['id'] in TARGETS, 'Unsupported CLI release target')
    # Development packages keep the Git-derived +g<sha> version. Release tags
    # have a stricter SemVer contract enforced by the candidate gate.
    require(isinstance(record['version'], str) and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]*', record['version']), 'Unsafe CLI version')
    return f"OpenTLV-CLI-{record['version']}-{record['id']}" + TARGETS[record['id']][3]


def expected_files(record):
    executable = 'otlv.exe' if record['id'].startswith('windows-') else 'otlv'
    return {'bin/' + executable, 'build-info.json', 'licenses/OpenTLV-CLI.txt',
            'licenses/OpenTLV.txt', 'licenses/nlohmann-json.txt'}


def check_target(path, identifier):
    """Check the actual executable header, not just the runner's machine label."""
    data = path.read_bytes()
    valid = False
    if identifier == 'linux-x64-static':
        valid = (data[:6] == b'\x7fELF\x02\x01' and len(data) >= 20 and
                 struct.unpack_from('<H', data, 18)[0] == 62)
    elif identifier == 'windows-x64-static' and data[:2] == b'MZ' and len(data) >= 64:
        offset = struct.unpack_from('<I', data, 60)[0]
        valid = (data[offset:offset + 4] == b'PE\0\0' and len(data) >= offset + 26 and
                 struct.unpack_from('<H', data, offset + 4)[0] == 0x8664 and
                 struct.unpack_from('<H', data, offset + 24)[0] == 0x20B)
    elif identifier == 'macos-arm64-static':
        valid = (data[:4] == b'\xcf\xfa\xed\xfe' and len(data) >= 8 and
                 struct.unpack_from('<I', data, 4)[0] == 0x0100000C)
    require(valid, 'Packaged executable OS/architecture mismatch')


def check_runtime(names, identifier):
    """Allow only the supported platform runtimes; reject build-local libraries."""
    patterns = {
        'linux-x64-static': r'(?:lib(?:c|m|dl|pthread|rt)\.so\.[0-9]+|libstdc\+\+\.so\.6|'
                            r'libgcc_s\.so\.1|ld-linux-x86-64\.so\.2)',
        'windows-x64-static': r'(?:kernel32|advapi32|user32|shell32|ole32|oleaut32|ws2_32|'
                              r'bcrypt|ntdll|ucrtbase|vcruntime140(?:_1)?|msvcp140(?:_1|_2)?|'
                              r'api-ms-win-crt-[a-z0-9-]+)\.dll',
        'macos-arm64-static': r'/usr/lib/(?:libSystem\.B|libc\+\+\.1|libc\+\+abi)\.dylib',
    }
    require(identifier in patterns and names and all(
        re.fullmatch(patterns[identifier], name, re.IGNORECASE if identifier.startswith('windows-') else 0)
        for name in names), 'Unexpected CLI runtime dependency')


def check_members(archive, record):
    """Reject extra paths, aliases, duplicates and non-regular members before extraction."""
    extension = TARGETS[record['id']][3]
    root = archive_name(record)[:-len(extension)]
    files = {root + '/' + name for name in expected_files(record)}
    directories = {root, root + '/bin', root + '/licenses'}
    seen = set()

    def member(name, directory, regular, mode):
        name = name[:-1] if directory and name.endswith('/') else name
        require(name not in seen, 'Duplicate CLI archive member')
        seen.add(name)
        require(name in (directories if directory else files) and (directory or regular),
                'Unexpected CLI archive member')
        require(not mode & 0o7000, 'Unsafe CLI archive permissions')
        if name == root + '/bin/otlv':
            require(mode & 0o111, 'Packaged CLI is not executable')

    if extension == '.zip':
        with zipfile.ZipFile(archive) as source:
            for item in source.infolist():
                mode = item.external_attr >> 16
                member(item.filename, item.is_dir(), (mode & 0o170000) in (0, 0o100000), mode)
    else:
        with tarfile.open(archive, 'r:gz') as source:
            for item in source:
                member(item.name, item.isdir(), item.isfile(), item.mode)
    require(files <= seen, 'Missing CLI archive files')
    return root


def smoke(cli, version, work):
    # Only platform runtime locations remain in PATH. Drop loader overrides so
    # developer build trees cannot supply a missing library during relocation.
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(('LD_', 'DYLD_'))}
    environment['PATH'] = (str(Path(os.environ['SystemRoot']) / 'System32')
                           if platform.system() == 'Windows' else '/usr/bin:/bin')
    environment.update(NO_COLOR='1', TERM='dumb')

    def invoke(args, code=0, stdout=b'', stderr=b''):
        result = subprocess.run([str(cli), *args], cwd=work, env=environment, input=b'',
                                capture_output=True, timeout=20, check=False)
        require(result.returncode == code and result.stderr.replace(b'\r\n', b'\n') == stderr and
                (stdout is None or result.stdout.replace(b'\r\n', b'\n') == stdout),
                f'Packaged CLI smoke failed: {args}: {result!r}')
        return result.stdout

    invoke(['--version'], stdout=f'OpenTLV CLI {version}\n'.encode())
    require(b'Usage:' in invoke(['--help'], stdout=None), 'Packaged CLI help mismatch')
    invoke(['encode', '--format', 'fixed', '--tag', '04', '--value', 'AA',
            '--output-encoding', 'binary', '--output-file', 'smoke.bin'])
    require((work / 'smoke.bin').read_bytes() == bytes.fromhex('0401AA'), 'Packaged CLI encode mismatch')
    invoke(['dump', '--format', 'fixed', '--input', 'smoke.bin'],
           stdout=b'offset=0 tag=04 length=1 value=AA\n')
    invoke(['validate', '--format', 'fixed', '--hex', '0402AA'], code=1,
           stderr=b'otlv: error: truncated input\n\ncode: TLV_ERR_TRUNCATED\n'
                  b'location: input point\noffset: 0x2 (2)\ntag: 04\nwhile reading: value\n'
                  b'raw length: 02\ndeclared length: 2\navailable: 1\n')
    return {'status': 'passed', 'cases': SMOKE_CASES}


def verify_archive(archive, record, *, native=False):
    """Inspect bytes everywhere; execute five checks only on the native producer."""
    require(archive.name == archive_name(record), 'Wrong CLI archive name')
    root = check_members(archive, record)
    with tempfile.TemporaryDirectory(prefix='cli-package-') as tmp:
        work = Path(tmp)
        extract(archive, work / 'relocated')
        stage = work / 'relocated' / root
        embedded = {key: value for key, value in record.items() if key not in PACKAGE_FIELDS}
        require(read(stage / 'build-info.json') == embedded, 'Packaged build metadata mismatch')
        for name in expected_files(record):
            require((stage / name).stat().st_size > 0, 'Empty CLI archive file')
        cli = stage / ('bin/otlv.exe' if record['id'].startswith('windows-') else 'bin/otlv')
        check_target(cli, record['id'])
        imports = check_static_core(cli)
        check_runtime(imports, record['id'])
        binary = record['provenance']['binary']
        require(digest(cli) == binary['sha256'] and imports == binary['runtime_imports'],
                'Packaged executable differs from verified build')
        result = {'schema': 1, 'target': record['id'], 'runtime_imports': imports,
                  'files': {name: digest(stage / name) for name in sorted(expected_files(record))}}
        if native:
            require(native_id() == record['id'], 'Package smoke requires the native release target')
            result['smoke'] = smoke(cli, record['version'], work)
        return result
