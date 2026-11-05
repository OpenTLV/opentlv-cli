# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Real archive fixtures exercise the CLI publication boundary on every host."""

import io
from pathlib import Path
import shutil
import struct
import sys
import tarfile
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ci_support import digest, write
from release_artifacts import (TARGETS, archive_name, check_runtime,
                               check_target, expected_files, smoke, verify_archive)
from test_ci_linkage import elf, macho, pe


def fixture_binary(identifier):
    if identifier.startswith('windows-'):
        return pe(['KERNEL32.dll'])
    if identifier.startswith('macos-'):
        data = bytearray(macho(['/usr/lib/libSystem.B.dylib']))
        struct.pack_into('<I', data, 4, 0x0100000C)
        return bytes(data)
    return elf(['libc.so.6'])


def fixture_archive(folder, record, change=None):
    extension = TARGETS[record['id']][3]
    name = archive_name(record)[:-len(extension)]
    stage = folder / 'stage' / name
    for file in expected_files(record):
        path = stage / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Fixture license text\n')
    cli = stage / ('bin/otlv.exe' if record['id'].startswith('windows-') else 'bin/otlv')
    cli.write_bytes(fixture_binary(record['id']))
    cli.chmod(0o755)
    record['provenance']['binary']['sha256'] = digest(cli)
    record['provenance']['binary']['runtime_imports'] = {
        'linux-x64-static': ['libc.so.6'], 'windows-x64-static': ['KERNEL32.dll'],
        'macos-arm64-static': ['/usr/lib/libSystem.B.dylib']}[record['id']]
    write(stage / 'build-info.json', record)
    if change:
        change(stage, cli)
    if extension == '.zip':
        return Path(shutil.make_archive(str(folder / name), 'zip', stage.parent, stage.name))
    archive = folder / (name + extension)

    def permissions(item):
        # Windows chmod does not store POSIX executable bits in fixtures.
        if item.name.endswith('/bin/otlv'):
            item.mode = 0o755
        return item

    with tarfile.open(archive, 'w:gz') as output:
        output.add(stage, arcname=name, filter=permissions)
    return archive


class Artifacts(unittest.TestCase):
    def record(self, identifier):
        return {'id': identifier, 'version': '0.3.0-rc.1', 'provenance': {'binary': {}}}

    def test_development_versions_remain_packagable_but_paths_are_rejected(self):
        record = self.record('linux-x64-static')
        record['version'] = '0.3.0-dev.1+g123456789abc.dirty'
        self.assertIn(record['version'], archive_name(record))
        for version in ('../escape', '/absolute', 'C:drive', 'with\\slash', ''):
            with self.subTest(version=version), self.assertRaises(ValueError):
                archive_name(record | {'version': version})

    def test_all_supported_archives_have_exact_inventory_and_binary_identity(self):
        for identifier in TARGETS:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as tmp:
                record = self.record(identifier)
                archive = fixture_archive(Path(tmp), record)
                verified = verify_archive(archive, record)
                self.assertEqual(set(verified['files']), expected_files(record))
                self.assertEqual(verified['target'], identifier)
                # Inspection on a foreign host never claims native execution.
                self.assertNotIn('smoke', verified)

    def test_archive_corruption_is_rejected_before_publication(self):
        def change(stage, cli, mode):
            if mode == 'extra':
                (stage / 'debug.pdb').write_bytes(b'development-only')
            elif mode == 'missing':
                (stage / 'licenses/OpenTLV.txt').unlink()
            elif mode == 'empty':
                (stage / 'licenses/OpenTLV.txt').write_bytes(b'')
            elif mode == 'metadata':
                write(stage / 'build-info.json', {'version': 'wrong'})
            elif mode == 'binary':
                cli.write_bytes(cli.read_bytes() + b'changed')
            elif mode == 'architecture':
                cli.write_bytes(pe(['KERNEL32.dll']))

        for mode in ('extra', 'missing', 'empty', 'metadata', 'binary', 'architecture'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                record = self.record('linux-x64-static')
                archive = fixture_archive(Path(tmp), record, lambda s, c: change(s, c, mode))
                with self.assertRaises(ValueError):
                    verify_archive(archive, record)

    def test_machine_headers_reject_other_architectures_on_each_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'binary'
            for identifier in TARGETS:
                data = bytearray(fixture_binary(identifier))
                if identifier.startswith('windows-'):
                    struct.pack_into('<H', data, 0x44, 0xAA64)
                elif identifier.startswith('macos-'):
                    struct.pack_into('<I', data, 4, 0x01000007)
                else:
                    struct.pack_into('<H', data, 18, 183)
                path.write_bytes(data)
                with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, 'architecture'):
                    check_target(path, identifier)

    def test_tar_links_special_files_duplicates_and_permissions_are_rejected(self):
        for mode in ('symlink', 'hardlink', 'fifo', 'duplicate', 'traversal', 'permission', 'setuid'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                record = self.record('linux-x64-static')
                archive = fixture_archive(Path(tmp), record)
                with tarfile.open(archive, 'r:gz') as source:
                    members = [(item, source.extractfile(item).read() if item.isfile() else None)
                               for item in source]
                with tarfile.open(archive, 'w:gz') as output:
                    for item, data in members:
                        if item.name.endswith('/bin/otlv'):
                            if mode in ('permission', 'setuid'):
                                item.mode = 0o644 if mode == 'permission' else 0o4755
                            if mode in ('symlink', 'hardlink', 'fifo'):
                                item.type = {'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE,
                                             'fifo': tarfile.FIFOTYPE}[mode]
                                item.linkname = 'elsewhere'
                                item.size = 0
                                data = None
                        output.addfile(item, io.BytesIO(data) if data is not None else None)
                    if mode in ('duplicate', 'traversal'):
                        item = tarfile.TarInfo(members[-1][0].name if mode == 'duplicate' else '../escape')
                        output.addfile(item, io.BytesIO())
                with self.assertRaises(ValueError):
                    verify_archive(archive, record)

    def test_zip_duplicate_and_symlink_are_rejected(self):
        for name in ('duplicate', 'symlink', 'extra'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                record = self.record('windows-x64-static')
                archive = fixture_archive(Path(tmp), record)
                root = archive.name[:-4]
                with zipfile.ZipFile(archive, 'a') as output:
                    item = zipfile.ZipInfo(root + ('/build-info.json' if name == 'duplicate' else '/extra'))
                    item.external_attr = (0o120777 if name == 'symlink' else 0o100644) << 16
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore', UserWarning)
                        output.writestr(item, 'target')
                with self.assertRaises(ValueError):
                    verify_archive(archive, record)

    def test_unexpected_runtime_libraries_fail_closed(self):
        allowed = {'linux-x64-static': ['libstdc++.so.6', 'libm.so.6', 'libgcc_s.so.1', 'libc.so.6'],
                   'windows-x64-static': ['KERNEL32.dll', 'MSVCP140.dll', 'VCRUNTIME140_1.dll',
                                          'api-ms-win-crt-runtime-l1-1-0.dll'],
                   'macos-arm64-static': ['/usr/lib/libSystem.B.dylib', '/usr/lib/libc++.1.dylib']}
        for identifier, names in allowed.items():
            check_runtime(names, identifier)
            for name in ('tlv.dll', 'libasan.so.8', '@rpath/libc++.1.dylib', '/tmp/libc.so.6',
                         'VCRUNTIME140D.dll', 'unexpected.dll'):
                with self.subTest(identifier=identifier, name=name), self.assertRaises(ValueError):
                    check_runtime(names + [name], identifier)

    def test_native_verification_requires_host_and_successful_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = self.record('linux-x64-static')
            archive = fixture_archive(Path(tmp), record)
            with patch('release_artifacts.native_id', return_value='macos-arm64-static'):
                with self.assertRaisesRegex(ValueError, 'native release target'):
                    verify_archive(archive, record, native=True)
            with patch('release_artifacts.native_id', return_value=record['id']), \
                    patch('release_artifacts.smoke', side_effect=ValueError('startup failed')):
                with self.assertRaisesRegex(ValueError, 'startup failed'):
                    verify_archive(archive, record, native=True)

    def test_smoke_requires_exit_status_streams_and_file_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                smoke(Path(sys.executable), '0.3.0', Path(tmp))


if __name__ == '__main__':
    unittest.main()
