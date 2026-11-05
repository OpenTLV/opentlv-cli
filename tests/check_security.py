#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Bounded CLI-owned security regressions using the existing process harness."""

import json
import sys

from check_executable import ProcessContract, main


class SecurityRegression(ProcessContract):
    def test_long_and_overflowing_arguments(self):
        self.invoke('x' * 4096, code=2, error='unknown command')
        for value in ('9' * 128, '-1', '1x'):
            with self.subTest(value=value):
                self.invoke('validate', '--format', 'fixed', '--max-input-size', value,
                            code=2, error='nonnegative')
        self.invoke('dump', '--format', 'fixed', '--hex', 'AA' * 2048,
                    '--max-input-size', '32', code=3, error='input-size limit exceeded')
        self.assertEqual(list(self.work.iterdir()), [])

    def test_input_limit_boundaries(self):
        wire = bytes.fromhex('04040A0D1AFF')
        (self.work / 'input.bin').write_bytes(wire)
        (self.work / 'input.hex').write_text(wire.hex(), encoding='ascii')
        cases = [(['--input', 'input.bin'], b''),
                 (['--input', 'input.hex', '--input-encoding', 'hex'], b''),
                 (['--input', '-'], wire),
                 (['--input', '-', '--input-encoding', 'hex'], wire.hex().encode('ascii'))]
        for args, stdin in cases:
            with self.subTest(args=args):
                self.invoke('validate', '--format', 'fixed', *args, '--max-input-size', '6', stdin=stdin)
                self.invoke('validate', '--format', 'fixed', *args, '--max-input-size', '5',
                            stdin=stdin, code=3, error='input-size limit exceeded')
        self.assertEqual((self.work / 'input.bin').read_bytes(), wire)

    def test_json_rejection_preserves_existing_output(self):
        output = self.work / 'existing.bin'
        output.write_bytes(b'sentinel')
        model = {'schema': 'opentlv.tlv', 'version': 1, 'format': 'fixed',
                 'elements': [{'tag': '04', 'value': 'AA'}]}
        documents = [b'{bad', b'[]', b'null', b'{"schema":"opentlv.tlv","schema":"duplicate"}',
                     json.dumps(model | {'elements': [None]}).encode(),
                     json.dumps(model | {'elements': [{'tag': '04', 'value': '\x00'}]}).encode(),
                     json.dumps(model | {'elements': [{'tag': '04', 'value': []}]}).encode()]
        for document in documents:
            with self.subTest(document=document):
                self.invoke('encode', '--format', 'fixed', '--output-file', output,
                            stdin=document, code=2, error='invalid JSON document')
                self.assertEqual(output.read_bytes(), b'sentinel')
        document = json.dumps(model).encode()
        self.invoke('encode', '--format', 'fixed', '--output-file', output,
                    '--max-input-size', str(len(document) - 1), stdin=document,
                    code=3, error='input-size limit exceeded')
        self.assertEqual(output.read_bytes(), b'sentinel')

    def test_json_ownership_and_element_limit(self):
        # Reallocation of the CLI SAX frame/element vectors must preserve
        # borrowed nodes, including while unwinding a rejected document.
        elements = [{'tag': '04', 'value': 'AA'} for _ in range(64)]
        model = {'schema': 'opentlv.tlv', 'version': 1, 'format': 'fixed', 'elements': elements}
        document = json.dumps(model).encode()
        self.invoke('encode', '--format', 'fixed', '--max-elements', '64',
                    stdin=document, stdout='0401AA' * 64 + '\n')
        self.invoke('encode', '--format', 'fixed', '--max-elements', '63',
                    stdin=document, code=3, error='element limit exceeded')
        self.require('BER')
        node = {'tag': '04', 'value': 'AA'}
        for _ in range(16):
            node = {'tag': '30', 'children': [node]}
        nested = json.dumps(model | {'format': 'ber', 'elements': [node]}).encode()
        self.invoke('encode', '--format', 'ber', '--max-depth', '8', stdin=nested,
                    code=3, error='nesting depth limit exceeded')
        self.invoke('encode', '--format', 'ber', '--max-depth', '32', stdin=nested, stdout=None)

    def test_output_paths_and_generation_cleanup(self):
        directory = self.work / 'output directory'
        directory.mkdir()
        self.invoke('encode', '--format', 'fixed', '--tag', '04', '--value', 'AA',
                    '--output-file', directory, code=3, error='cannot open output file')
        blocker = self.work / 'blocker'
        blocker.write_bytes(b'sentinel')
        self.invoke('generate', '--format', 'fixed', '--seed', '42', '--count', '1',
                    '--max-elements', '2', '--max-value-size', '8', '--max-case-size', '32',
                    '--output-dir', blocker / 'child', code=3, error='cannot create output directory')
        self.assertEqual(blocker.read_bytes(), b'sentinel')
        self.assertEqual(list(directory.iterdir()), [])
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ['blocker', 'output directory'])


if __name__ == '__main__':
    sys.exit(main(SecurityRegression))
