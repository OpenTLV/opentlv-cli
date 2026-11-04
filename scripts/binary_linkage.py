#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Read an executable's shared-library imports and reject a shared OpenTLV Core.

Parses ELF DT_NEEDED, PE import/delay-import and Mach-O dylib load commands
directly, so no platform tool (readelf, dumpbin, otool) is required. Only Core
linkage is policed; system runtime libraries remain dynamic by design.
"""

import argparse
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import struct
import sys

# Current tlv and future opentlv_<module> libraries, with any version suffix:
# tlv.dll, libtlv.so.1, libopentlv_core.0.dylib, opentlv-query.dll.
CORE_LIBRARY = re.compile(r'(?:lib)?(?:tlv|opentlv(?:[_-][0-9a-z_-]+)?)(?:\.[0-9a-z.]+)?', re.IGNORECASE)


class FormatError(ValueError):
    pass


def _cstring(data, offset):
    if not 0 <= offset < len(data):
        raise FormatError('String offset outside the binary')
    end = data.find(b'\0', offset)
    if end < 0:
        raise FormatError('Unterminated string')
    return data[offset:end].decode('utf-8', errors='replace')


def _unpack(fmt, data, offset):
    if offset < 0 or offset + struct.calcsize(fmt) > len(data):
        raise FormatError('Truncated binary')
    return struct.unpack_from(fmt, data, offset)


def elf_dependencies(data):
    wide = {1: False, 2: True}.get(data[4])
    order = {1: '<', 2: '>'}.get(data[5])
    if wide is None or order is None:
        raise FormatError('Unsupported ELF class or byte order')
    if wide:
        shoff, = _unpack(order + 'Q', data, 0x28)
        shentsize, shnum = _unpack(order + 'HH', data, 0x3A)
        section, dynamic = order + 'IIQQQQIIQQ', order + 'qQ'
    else:
        shoff, = _unpack(order + 'I', data, 0x20)
        shentsize, shnum = _unpack(order + 'HH', data, 0x2E)
        section, dynamic = order + 'IIIIIIIIII', order + 'iI'
    sections = []
    for index in range(shnum):
        fields = _unpack(section, data, shoff + index * shentsize)
        # name, type, flags, addr, offset, size, link, ...
        sections.append((fields[1], fields[4], fields[5], fields[6]))
    names = []
    for kind, offset, size, link in sections:
        if kind != 6:  # SHT_DYNAMIC
            continue
        if link >= len(sections):
            raise FormatError('Dynamic string table index outside the binary')
        strings = sections[link][1]
        step = struct.calcsize(dynamic)
        for position in range(offset, offset + size, step):
            tag, value = _unpack(dynamic, data, position)
            if tag == 0:  # DT_NULL
                break
            if tag == 1:  # DT_NEEDED
                names.append(_cstring(data, strings + value))
    return names


def pe_dependencies(data):
    header, = _unpack('<I', data, 0x3C)
    if data[header:header + 4] != b'PE\0\0':
        raise FormatError('Missing PE signature')
    sections_count, optional_size = _unpack('<H12xH', data, header + 6)
    optional = header + 24
    magic, = _unpack('<H', data, optional)
    if magic == 0x20B:
        image_base, = _unpack('<Q', data, optional + 24)
        directories = optional + 112
        count, = _unpack('<I', data, optional + 108)
    elif magic == 0x10B:
        image_base, = _unpack('<I', data, optional + 28)
        directories = optional + 96
        count, = _unpack('<I', data, optional + 92)
    else:
        raise FormatError('Unsupported PE optional header')
    table = optional + optional_size
    sections = [_unpack('<8xIIII', data, table + index * 40) for index in range(sections_count)]

    def offset(rva):
        for virtual_size, address, raw_size, raw in sections:
            if address <= rva < address + max(virtual_size, raw_size):
                return raw + rva - address
        raise FormatError('RVA outside every PE section')

    def directory(index):
        return _unpack('<II', data, directories + index * 8) if index < count else (0, 0)

    names = []
    imports, _ = directory(1)
    if imports:
        position = offset(imports)
        while True:
            descriptor = _unpack('<IIIII', data, position)
            if not any(descriptor):
                break
            names.append(_cstring(data, offset(descriptor[3])))
            position += 20
    delayed, _ = directory(13)
    if delayed:
        position = offset(delayed)
        while True:
            attributes, name = _unpack('<II', data, position)
            if not name:
                break
            # Attribute bit 0 marks RVAs; legacy descriptors hold virtual addresses.
            names.append(_cstring(data, offset(name if attributes & 1 else name - image_base)))
            position += 32
    return names


LOAD_DYLIB = {0xC, 0x20, 0x80000018, 0x8000001F, 0x80000023}


def macho_dependencies(data, start=0):
    magic = data[start:start + 4]
    order = '<' if magic in (b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe') else '>'
    wide = magic in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf')
    commands, = _unpack(order + 'I', data, start + 16)
    position = start + (32 if wide else 28)
    names = []
    for _ in range(commands):
        command, size = _unpack(order + 'II', data, position)
        if size < 8:
            raise FormatError('Invalid Mach-O load command size')
        if command in LOAD_DYLIB:
            name, = _unpack(order + 'I', data, position + 8)
            names.append(_cstring(data, position + name))
        position += size
    return names


def fat_dependencies(data):
    wide = data[:4] == b'\xca\xfe\xba\xbf'
    count, = _unpack('>I', data, 4)
    names = []
    for index in range(count):
        if wide:
            start, = _unpack('>8xQ', data, 8 + index * 32)
        else:
            start, = _unpack('>8xI', data, 8 + index * 20)
        names += [name for name in macho_dependencies(data, start) if name not in names]
    return names


def dependencies(path):
    """Return the shared libraries an executable names, in load-command order."""
    data = Path(path).read_bytes()
    if data[:4] == b'\x7fELF':
        return elf_dependencies(data)
    if data[:2] == b'MZ':
        return pe_dependencies(data)
    if data[:4] in (b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf'):
        return macho_dependencies(data)
    if data[:4] in (b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
        return fat_dependencies(data)
    raise FormatError(f'Unsupported executable format: {path}')


def core_library(name):
    # Mach-O names are paths such as @rpath/libtlv.dylib; PE names are bare.
    base = PureWindowsPath(name).name if '\\' in name else PurePosixPath(name).name
    return CORE_LIBRARY.fullmatch(base) is not None


def check_static_core(path):
    """Fail unless the executable imports libraries, none of them OpenTLV Core."""
    names = dependencies(path)
    # A parser that silently finds nothing must not pass as "static".
    if not names:
        raise FormatError(f'No shared-library imports found in {path}; cannot verify Core linkage')
    core = [name for name in names if core_library(name)]
    if core:
        raise ValueError(f'{path} depends on a shared OpenTLV Core library: {", ".join(core)}. '
                         'The standalone CLI must link Core statically.')
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    try:
        names = check_static_core(args.executable)
    except (OSError, ValueError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1
    print(f'PASS: {args.executable.name} links OpenTLV Core statically; shared imports: {", ".join(names)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
