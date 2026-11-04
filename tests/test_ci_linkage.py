# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Binary import parsing proves static Core linkage on ELF, PE and Mach-O."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from binary_linkage import FormatError, check_static_core, core_library, dependencies


def elf(names):
    strings = b'\0' + b''.join(name.encode() + b'\0' for name in names)
    offsets = [1 + sum(len(n) + 1 for n in names[:i]) for i in range(len(names))]
    dynamic = b''.join(struct.pack('<qQ', 1, offset) for offset in offsets) + struct.pack('<qQ', 0, 0)
    strtab, dyn = 64, 64 + len(strings)
    shoff = dyn + len(dynamic)
    header = (b'\x7fELF' + bytes([2, 1, 1]) + bytes(9) +
              struct.pack('<HHIQQQIHHHHHH', 3, 62, 1, 0, 0, shoff, 0, 64, 56, 0, 64, 3, 0))
    sections = (bytes(64) + struct.pack('<IIQQQQIIQQ', 0, 3, 0, 0, strtab, len(strings), 0, 0, 1, 0) +
                struct.pack('<IIQQQQIIQQ', 0, 6, 0, 0, dyn, len(dynamic), 1, 0, 8, 16))
    return header + strings + dynamic + sections


def pe(names, delayed=()):
    image = bytearray(0x2000)
    image[:2] = b'MZ'
    struct.pack_into('<I', image, 0x3C, 0x40)
    image[0x40:0x44] = b'PE\0\0'
    struct.pack_into('<HH12xHH', image, 0x44, 0x8664, 1, 240, 0x22)
    optional = 0x58
    struct.pack_into('<H', image, optional, 0x20B)
    struct.pack_into('<Q', image, optional + 24, 0x140000000)
    struct.pack_into('<I', image, optional + 108, 16)
    struct.pack_into('<II', image, optional + 112 + 8, 0x1000, 20 * (len(names) + 1))
    if delayed:
        struct.pack_into('<II', image, optional + 112 + 13 * 8, 0x1200, 32 * (len(delayed) + 1))
    struct.pack_into('<8sIIII', image, optional + 240, b'.idata', 0x1000, 0x1000, 0x1000, 0x400)

    def place(rva, text):
        image[0x400 + rva - 0x1000:0x400 + rva - 0x1000 + len(text) + 1] = text.encode() + b'\0'

    name = 0x1100
    for index, value in enumerate(names):
        struct.pack_into('<IIIII', image, 0x400 + index * 20, 0x1800, 0, 0, name, 0x1900)
        place(name, value)
        name += 0x20
    name = 0x1300
    for index, value in enumerate(delayed):
        struct.pack_into('<II', image, 0x400 + 0x200 + index * 32, 1, name)
        place(name, value)
        name += 0x20
    return bytes(image)


def macho(names):
    commands = struct.pack('<II16s', 0x1B, 24, bytes(16))  # LC_UUID, skipped
    for name in names:
        payload = name.encode() + b'\0'
        payload += bytes(-(24 + len(payload)) % 8)
        commands += struct.pack('<IIIIII', 0xC, 24 + len(payload), 24, 2, 0x10000, 0x10000) + payload
    return (b'\xcf\xfa\xed\xfe' + struct.pack('<iiIIIII', 0x01000007, 3, 2, len(names) + 1,
                                              len(commands), 0, 0) + commands)


def fat(thin):
    return struct.pack('>IIiiIII', 0xCAFEBABE, 1, 0x01000007, 3, 4096, len(thin), 12) + bytes(4096 - 28) + thin


class Linkage(unittest.TestCase):
    def parse(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'otlv'
            path.write_bytes(data)
            return dependencies(path)

    def verify(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'otlv'
            path.write_bytes(data)
            return check_static_core(path)

    def test_each_format_lists_imports(self):
        system = ['libstdc++.so.6', 'libc.so.6']
        self.assertEqual(self.parse(elf(system)), system)
        self.assertEqual(self.parse(pe(['KERNEL32.dll'], ['USER32.dll'])), ['KERNEL32.dll', 'USER32.dll'])
        libraries = ['/usr/lib/libc++.1.dylib', '/usr/lib/libSystem.B.dylib']
        self.assertEqual(self.parse(macho(libraries)), libraries)
        self.assertEqual(self.parse(fat(macho(libraries))), libraries)

    def test_static_core_passes_and_shared_core_fails(self):
        self.assertEqual(self.verify(elf(['libc.so.6'])), ['libc.so.6'])
        cases = (elf(['libtlv.so.0', 'libc.so.6']), pe(['tlv.dll', 'KERNEL32.dll']),
                 pe(['KERNEL32.dll'], ['TLV.DLL']), macho(['@rpath/libtlv.dylib']),
                 fat(macho(['@rpath/libopentlv_core.0.dylib'])), elf(['libopentlv-query.so']))
        for index, data in enumerate(cases):
            with self.subTest(case=index), self.assertRaisesRegex(ValueError, 'shared OpenTLV Core'):
                self.verify(data)

    def test_no_imports_or_unknown_format_cannot_pass(self):
        with self.assertRaisesRegex(FormatError, 'No shared-library imports'):
            self.verify(elf([]))
        with self.assertRaisesRegex(FormatError, 'Unsupported executable format'):
            self.verify(b'#!/bin/sh\n')
        with self.assertRaises(FormatError):
            self.verify(elf(['libc.so.6'])[:100])

    def test_core_names_are_matched_precisely(self):
        for name in ('tlv.dll', 'libtlv.so', 'libtlv.so.1', '@rpath/libtlv.0.8.0.dylib',
                     'C:\\Core\\bin\\tlv.dll', 'opentlv_core.dll', 'libopentlv_io.so.1'):
            self.assertTrue(core_library(name), name)
        for name in ('libtlvx.so', 'mytlv.dll', 'KERNEL32.dll', 'libstdc++.so.6', 'libtlv++helper.so'):
            self.assertFalse(core_library(name), name)

    def test_running_interpreter_is_parsed(self):
        # A real platform binary guards the parser against synthetic-only layouts.
        self.assertTrue(dependencies(sys.executable))


if __name__ == '__main__':
    unittest.main()
