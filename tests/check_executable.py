#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""CLI-owned process contracts; no Core imports or candidate-generated snapshots."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


def text(data):
    # Only textual streams permit platform newline normalization. Binary streams
    # and all file contents are compared byte-for-byte.
    return data.decode("utf-8").replace("\r\n", "\n")


class ExecutableRegression(unittest.TestCase):
    cli: Path
    version: str
    features: set[str]

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="otlv-regression-")
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)

    def require(self, *features):
        missing = set(features) - self.features
        if missing:
            self.skipTest("selected Core disables " + ", ".join(sorted(missing)))

    def invoke(self, *args, code=0, stdout="", stderr="", error=None, stdin=b""):
        result = subprocess.run(
            [str(self.cli), *map(str, args)], cwd=self.work, input=stdin,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
            env=dict(os.environ, NO_COLOR="1", TERM="dumb"), check=False,
        )
        context = f"otlv {args!r}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        self.assertEqual(result.returncode, code, context)
        if stdout is not None:
            actual = result.stdout if isinstance(stdout, bytes) else text(result.stdout)
            self.assertEqual(actual, stdout, context)
        if error is not None:
            self.assertTrue(text(result.stderr).startswith("otlv: "), context)
            self.assertIn(error, text(result.stderr), context)
        elif stderr is not None:
            self.assertEqual(text(result.stderr), stderr, context)
        return result

    def json_output(self, *args, **kwargs):
        return json.loads(self.invoke(*args, stdout=None, **kwargs).stdout)

    def test_help(self):
        output = text(self.invoke("--help", stdout=None).stdout)
        self.assertIn("Usage:", output)
        for command in ("formats", "dump", "validate", "decode", "query",
                        "diff", "generate", "encode", "completion"):
            self.assertIn(command, output)

    def test_version(self):
        self.invoke("--version", stdout=f"OpenTLV CLI {self.version}\n")

    def test_formats(self):
        formats = [("FIXED", "fixed"), ("EMV", "emv"), ("BER", "ber"),
                   ("DER", "der"), ("BLUETOOTH_LTV", "bluetooth-ltv"), ("NFC", "nfc-type2")]
        self.invoke("formats", stdout="".join(name + "\n" for flag, name in formats
                                             if flag in self.features))

    def test_argument_errors(self):
        cases = [
            ([], "missing command"),
            (["unknown"], "unknown command"),
            (["help"], "unknown command"),
            (["version"], "unknown command"),
            (["dump", "--hex"], "missing option value"),
            (["dump", "--hex", "0400"], "requires --format"),
            (["dump", "--format", "unknown"], "unknown or disabled format"),
            (["dump", "--format", "fixed", "--format", "fixed"], "duplicate option"),
            (["dump", "--format", "fixed", "--unknown"], "unknown option"),
            (["dump", "--format", "fixed", "--input", "-", "--hex", "0400"],
             "--input and --hex cannot both be given"),
            (["dump", "--format", "fixed", "--force-color", "--no-color"], "conflicting color"),
            (["validate", "--format", "fixed", "--max-elements", "-1"], "nonnegative"),
            (["completion"], "requires a shell"),
            (["completion", "unknown"], "unknown shell"),
            (["completion", "bash", "extra"], "exactly one shell"),
            (["generate"], "requires --format"),
            (["generate", "--format", "fixed", "--seed", "-1", "--count", "1",
              "--output-dir", "out"], "seed/count"),
        ]
        for args, error in cases:
            with self.subTest(args=args):
                self.invoke(*args, code=2, error=error)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_input_sources_and_binary_stdin(self):
        # CR, LF, Ctrl-Z and a high byte catch text-mode pipe/file regressions.
        wire = bytes.fromhex("04040A0D1AFF")
        expected = "offset=0 tag=04 length=4 value=0A0D1AFF\n"
        (self.work / "input with spaces.bin").write_bytes(wire)
        (self.work / "input.hex").write_bytes(b"04 04\r\n0a 0D 1a ff\n")
        cases = [(["--hex", wire.hex()], b""),
                 (["--input", "input with spaces.bin"], b""),
                 (["--input", "input.hex", "--input-encoding", "hex"], b""),
                 (["--input", "-"], wire), ([], wire),
                 (["--input-encoding", "hex"], b"04 04\n0A0D1AFF")]
        for args, stdin in cases:
            with self.subTest(args=args):
                self.invoke("dump", "--format", "fixed", *args, stdin=stdin, stdout=expected)
        self.assertEqual((self.work / "input with spaces.bin").read_bytes(), wire)

    def test_empty_and_invalid_inputs(self):
        (self.work / "empty.bin").write_bytes(b"")
        (self.work / "invalid.bin").write_bytes(bytes.fromhex("0402AA"))
        for args in (["--hex", ""], ["--input", "empty.bin"], []):
            with self.subTest(args=args):
                self.invoke("validate", "--format", "fixed", *args)
        self.invoke("validate", "--format", "fixed", "--input", "invalid.bin",
                    code=1, error="truncated input")
        for value in ("0", "0G", "0 4", "0x04"):
            with self.subTest(value=value):
                self.invoke("dump", "--format", "fixed", "--hex", value, code=2,
                            stderr="otlv: hex input requires complete hexadecimal byte pairs\n")

    def test_file_errors_and_limits(self):
        # A file used as a parent is inaccessible on Windows and POSIX, even
        # under elevated accounts; chmod-based tests would not be portable.
        (self.work / "blocker").write_bytes(b"sentinel")
        for name in ("missing.bin", "blocker/input.bin"):
            with self.subTest(name=name):
                self.invoke("dump", "--format", "fixed", "--input", name, code=3,
                            stderr="otlv: cannot open input file\n")
        self.invoke("encode", "--format", "fixed", "--tag", "04", "--value", "AA",
                    "--output-file", "blocker/out.bin", code=3,
                    stderr="otlv: cannot open output file\n")
        self.invoke("validate", "--format", "fixed", "--hex", "0401AA",
                    "--max-input-size", "2", code=3, stderr="otlv: input-size limit exceeded\n")
        self.assertEqual((self.work / "blocker").read_bytes(), b"sentinel")
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ["blocker"])

    def test_human_and_compact_diagnostics(self):
        expected = {
            "human": "otlv: error: truncated input\n\ncode: TLV_ERR_TRUNCATED\n"
                     "location: input point\noffset: 0x2 (2)\ntag: 04\nwhile reading: value\n"
                     "raw length: 02\ndeclared length: 2\navailable: 1\n",
            "compact": "otlv: TLV_ERR_TRUNCATED at byte 2 tag=04 while reading value; "
                       "raw_length=02; declared_length=2; available=1: truncated input; "
                       "location=input:point\n",
        }
        for mode, diagnostic in expected.items():
            with self.subTest(mode=mode):
                self.invoke("validate", "--format", "fixed", "--hex", "0402AA",
                            "--diagnostics", mode, code=1, stderr=diagnostic)

    def test_json_diagnostics(self):
        result = self.invoke("validate", "--format", "fixed", "--hex", "0402AA",
                             "--diagnostics", "json", code=1, stderr=None)
        self.assertEqual(json.loads(result.stderr), {
            "available": 1, "code": "TLV_ERR_TRUNCATED", "declared_length": 2,
            "enclosing_end": 3, "length_offset": 1,
            "location": {"begin": 2, "domain": "input", "end": 2, "kind": "point"},
            "message": "truncated input", "offset": 2, "operation": "value",
            "raw_length": "02", "required": 2, "severity": "error", "tag": "04",
            "tag_offset": 0, "value_offset": 2,
        })

    def test_dump_json_and_color(self):
        args = ("dump", "--format", "fixed", "--hex", "0401aa")
        expected = "offset=0 tag=04 length=1 value=AA\n"
        self.invoke(*args, stdout=expected)
        self.invoke(*args, "--no-color", stdout=expected)
        colored = text(self.invoke(*args, "--force-color", stdout=None).stdout)
        self.assertIn("\x1b[", colored)
        self.assertEqual(self.json_output(*args, "--output", "json"), {
            "elements": [{"length": 1, "offset": 0, "tag": "04", "value": "AA"}],
        })

    def test_decode_encode_document_and_binary_output(self):
        model = {"schema": "opentlv.tlv", "version": 1, "format": "fixed",
                 "elements": [{"tag": "04", "value": "0A0D1AFF"}]}
        wire = bytes.fromhex("04040A0D1AFF")
        self.assertEqual(self.json_output("decode", "--format", "fixed", "--hex", wire.hex()), model)
        document = json.dumps(model).encode("utf-8")
        self.invoke("encode", "--format", "fixed", stdin=document, stdout="04040A0D1AFF\n")
        self.invoke("encode", "--format", "fixed", "--input", "-",
                    "--output-encoding", "binary", stdin=document, stdout=wire)
        (self.work / "document.json").write_bytes(document)
        for encoding, expected in (("binary", wire), ("hex", b"04040A0D1AFF\n")):
            with self.subTest(encoding=encoding):
                self.invoke("encode", "--format", "fixed", "--input", "document.json",
                            "--output-encoding", encoding, "--output-file", "output.bin")
                self.assertEqual((self.work / "output.bin").read_bytes(), expected)
        self.invoke("encode", "--format", "fixed", "--tag", "04", "--value", "AA",
                    stdout="0401AA\n")

    def test_encode_rejects_json_without_creating_output(self):
        for document, error in ((b"{bad", "invalid JSON document"),
                                (b'{"schema":"opentlv.tlv","version":2,"format":"fixed",'
                                 b'"elements":[]}', "unsupported JSON schema version")):
            with self.subTest(document=document):
                self.invoke("encode", "--format", "fixed", "--output-file", "out.bin",
                            stdin=document, code=2, error=error)
                self.assertFalse((self.work / "out.bin").exists())

    def test_tree_partial_output_and_recovery(self):
        self.require("BER")
        self.invoke("dump", "--format", "ber", "--hex", "E1035A0112", "--tree",
                    stdout="offset=0 tag=E1 length=3 value=5A0112\n"
                           "  offset=2 tag=5A length=1 value=12\n")
        self.invoke("dump", "--format", "ber", "--hex", "0401AA04", code=1,
                    stdout="offset=0 tag=04 length=1 value=AA\n", error="truncated input")
        result = self.invoke("dump", "--format", "ber", "--hex", "5A011200005A0134",
                             "--recover", "--diagnostics", "compact", code=4,
                             stdout="offset=0 tag=5A length=1 value=12\n"
                                    "skipped offset=3 length=2 error=TLV_ERR_INVALID_TAG "
                                    "error-location=input:point:3\n"
                                    "offset=5 tag=5A length=1 value=34\n",
                             error="output is incomplete")
        self.assertIn("skipped 2 byte(s) at offset 3", text(result.stderr))

    def test_query_path_scalar_and_no_match(self):
        self.require("BER", "QUERY_FRONTEND")
        args = ("--format", "ber", "--hex", "E10450024142")
        self.invoke("query", "E1/50", *args, "--value", stdout="4142\n")
        self.assertEqual(self.json_output("query", "E1/50", *args, "--output", "json"), {
            "matches": [{"length": 2, "offset": 2, "path": "E1/50", "tag": "50", "value": "4142"}],
        })
        self.assertEqual(self.json_output("query", "--query", "count(//50)", *args,
                                         "--output", "json"), {"type": 2, "value": 1})
        self.invoke("query", "E1/51", *args, code=5, stderr="otlv: no match for query E1/51\n")
        self.invoke("query", "E1/50", *args, "--value", "--output", "json",
                    code=2, error="--value")

    def test_query_variable_and_explain_streams(self):
        self.require("BER", "QUERY_FRONTEND")
        result = self.invoke("query", "--query", "count(//50[value(.) = $wanted])",
                             "--var", "wanted:bytes=4142", "--format", "ber",
                             "--hex", "50024142", "--explain", stdout="1\n", stderr=None)
        explanation = json.loads(result.stderr)
        self.assertEqual(explanation["backend"], "streaming-retained")
        self.assertEqual(explanation["query"], "count(//50[value(.) = $wanted])")
        # Workspace sizing and the documented unstable IR are deliberately not snapshots.

    def test_diff_files(self):
        self.require("BER", "QUERY_FRONTEND", "DOCUMENT")
        (self.work / "left.bin").write_bytes(bytes.fromhex("0401AA"))
        (self.work / "right.bin").write_bytes(bytes.fromhex("0401BB"))
        args = ("diff", "--format", "ber", "--input", "left.bin")
        self.invoke(*args, "--against", "left.bin")
        self.invoke(*args, "--against", "right.bin", stdout="changed /04[1]\n")
        self.assertEqual(self.json_output(*args, "--against", "right.bin", "--output", "json"), {
            "changes": [{"kind": "changed", "left": {"constructed": False, "value": "AA"},
                         "path": "/04[1]", "right": {"constructed": False, "value": "BB"}}],
        })
        self.invoke(*args, "--against", "right.bin", "--where", "//05")
        self.invoke(*args, code=2, error="--against")

    def test_tag_and_tags(self):
        self.require("EMV")
        self.invoke("tag", "9F02", "--module", "emv", stdout=
                    "Tag:         9F02\nName:        Amount Authorised\n"
                    "Type:        Numeric value (binary or decimal BCD, tag-dependent)\n"
                    "Form:        Primitive\nLength:      6\n")
        known = self.json_output("tag", "9F02", "--module", "emv", "--output", "json")
        self.assertIs(known["known"], True)
        self.assertEqual((known["tag"], known["module"], known["min_length"], known["max_length"]),
                         ("9F02", "emv", 6, 6))
        unknown = self.json_output("tag", "DF01", "--module", "emv", "--output", "json")
        self.assertEqual(unknown, {"known": False, "module": "emv", "tag": "DF01"})
        results = []
        for search in ("Amount", "aMoUnT"):
            result = self.json_output("tags", "--module", "emv", "--search", search, "--output", "json")
            self.assertEqual(result["module"], "emv")
            self.assertEqual([tag["tag"] for tag in result["tags"]], ["81", "9F02", "9F03", "9F04", "9F3A"])
            results.append(result)
        self.assertEqual(*results)
        self.invoke("tags", "--module", "emv", "--search", "no-such-tag-name")
        self.assertEqual(self.json_output("tags", "--module", "emv", "--search", "no-such-tag-name",
                                         "--output", "json"), {"module": "emv", "tags": []})
        self.invoke("tag", "9F", "--module", "emv", code=2, error="tag")

    def test_json_escaping(self):
        self.require("BLUETOOTH_LTV")
        value = b'A"\\\x00\t\nB'
        wire = bytes([len(value) + 1, 9]) + value
        result = self.invoke("dump", "--format", "bluetooth-ltv", "--module", "bluetooth",
                             "--decode", "--output", "json", "--hex", wire.hex(), stdout=None)
        self.assertEqual(json.loads(result.stdout)["elements"][0]["decoded"], value.decode("utf-8"))
        self.assertNotIn(b"\x00", result.stdout)

    def test_generate_files_replay_and_no_overwrite(self):
        args = ("generate", "--format", "fixed", "--seed", "42", "--count", "2",
                "--max-elements", "2", "--max-value-size", "8", "--max-case-size", "32")
        for directory, encoding in (("first", "bin"), ("replay", "bin"), ("json", "json")):
            self.invoke(*args, "--output-dir", directory, "--output-encoding", encoding)
            self.assertEqual(sorted(p.name for p in (self.work / directory).iterdir()),
                             [f"00000{index}.{encoding}" for index in range(2)])
        for index in range(2):
            name = f"00000{index}"
            wire = (self.work / "first" / (name + ".bin")).read_bytes()
            self.assertTrue(wire)
            self.assertEqual(wire, (self.work / "replay" / (name + ".bin")).read_bytes())
            model = json.loads((self.work / "json" / (name + ".json")).read_bytes())
            self.assertEqual(model["schema"], "opentlv.tlv")
            self.assertEqual(model["version"], 1)
            self.assertEqual(model["format"], "fixed")
            self.invoke("encode", "--format", "fixed", "--output-encoding", "binary",
                        stdin=json.dumps(model).encode("utf-8"), stdout=wire)
        before = {p.name: p.read_bytes() for p in (self.work / "first").iterdir()}
        self.invoke(*args, "--output-dir", "first", code=3, error="refusing to overwrite case")
        self.assertEqual({p.name: p.read_bytes() for p in (self.work / "first").iterdir()}, before)

    def test_completion(self):
        commands = ["dump", "validate", "decode", "query", "generate", "encode"]
        if "DOCUMENT" in self.features:
            commands.append("diff")
        if "EMV" in self.features:
            commands.extend(("tag", "tags"))
        for shell, header, registration in (
            ("bash", "# bash completion for otlv", "complete -F"),
            ("zsh", "#compdef otlv", "_describe 'command' commands"),
            ("fish", "# fish completion for otlv", "complete -c otlv"),
            ("powershell", "# PowerShell completion for otlv", "Register-ArgumentCompleter"),
        ):
            with self.subTest(shell=shell):
                result = text(self.invoke("completion", shell, stdout=None).stdout)
                self.assertTrue(result.startswith(header + "\n"))
                self.assertIn(registration, result)
                for command in commands:
                    self.assertIn(command, result)
                self.assertIn("max-case-size", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--version-file", required=True, type=Path)
    parser.add_argument("--features", nargs="+", required=True,
                        choices=("FIXED", "BER", "DER", "EMV", "BLUETOOTH_LTV", "NFC",
                                 "QUERY_FRONTEND", "DOCUMENT"))
    args = parser.parse_args()
    ExecutableRegression.cli = args.cli.resolve(strict=True)
    ExecutableRegression.version = args.version_file.read_text(encoding="utf-8").strip()
    ExecutableRegression.features = set(args.features)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExecutableRegression)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
