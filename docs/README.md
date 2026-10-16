# Command-line tool

The `otlv` executable inspects and structurally validates TLV
data, converts it to and from a [versioned JSON document](json-schema.md), and
recovers elements from damaged input, using the public C library through the
`tlv++` wrapper. Building it
requires a C++11 (or newer) compiler; the underlying library itself remains a
dependency-free C99 core, so this requirement affects only the CLI target.

## First inspection

Prerequisite: an installed `otlv` executable. If you need to build it, follow
[Build and install](#build-and-install) below.

```sh
otlv dump --format fixed --hex "01 02 48 69"
```

Expected output:

```text
offset=0 tag=01 length=2 value=4869
```

This input contains tag `01` with the two Value bytes of `Hi`. Fixed defaults
to one tag byte and one big-endian length byte. The tool requires an explicit
format and checks errors; it does not detect the format or infer Value semantics.
Next, try [commands](#commands) for files, nested data and validation.

## Build and install

Build from the standalone `opentlv-cli` repository:

```sh
cmake --preset default
cmake --build --preset default
ctest --preset default
cmake --install build/default --config Release --prefix install-cli
```

The executable is installed in the standard runtime directory (normally `bin`).
The [repository README](../README.md#standalone-build) describes dependencies,
workspace and offline builds, installed Core packages, and shared runtime
installation. `OPENTLV_CLI_BUILD_TESTS` controls CLI regression tests and
dependency smoke tests. The CLI requires Core's public C and C++ targets.
JSON input and output use the private header-only nlohmann/json dependency.

See [C++ and CLI examples](https://github.com/OpenTLV/opentlv/blob/edebe957ee2a1e0bf5685c3bd55a33788446e80d/docs/guides/cxx-examples.md#equivalent-cli-operations)
for matching parsing, nested writing and Query operations with executable
acceptance checks.

The [CLI migration regression baseline](../tests/baseline/README.md)
records the originating source revision, commands, test/fixture ownership and
the exact-output comparison procedure for standalone CLI extraction.
Its original Core-relative paths describe the historical source layout; see
[tests](../tests/README.md) for commands in this repository.

## Commands

```sh
otlv --help
otlv --version
otlv formats
otlv dump --format ber --hex "E1 03 5A 01 12" --tree
otlv dump --format fixed --input sample.bin
otlv dump --format bluetooth-ltv --hex "02 01 06 03 09 48 69"
otlv validate --format der --input sample.der
otlv validate --format ber --input -
otlv dump --format ber --module emv --hex "6F0784050102030405" --pretty --describe
otlv dump --format ber --input capture.hex --input-encoding hex
otlv dump --format ber --module emv --decode --hex "9F0206000000001000"
otlv dump --format ber --module emv --decode --output json --hex "9F0206000000001000"
otlv validate --format ber --module emv --input input.bin
otlv encode --format ber --tag 9F02 --value 000000001000
otlv decode --format ber --module emv --input capture.bin > capture.json
otlv encode --format ber --input capture.json --output-encoding binary --output-file out.bin
otlv dump --format ber --input damaged.bin --recover --tree
otlv validate --format ber --module emv --emv-check dictionary --hex "9F02050000000010"
otlv tag 9F02 --module emv
otlv query 6F/A5/50 --format ber --input card.bin --value
otlv completion bash
cat capture.bin | otlv dump --format ber --output json | jq '.elements'
```

`dump`, `validate`, `decode` and `query` require an explicit `--format`; `--input`
and `--hex` cannot both be given. `--input -` (or a bare `--input PATH`) reads
binary stdin, including on Windows, and so does omitting both `--input` and
`--hex` entirely, letting these commands sit in the middle of a shell
pipeline (`cat capture.bin | otlv dump --format ber`) without an explicit `-`.
`encode` reads its `--tag`/`--value` construction from the command line, but
falls back to reading its JSON document from stdin the same way when neither
`--tag` nor `--input` is given. Command output always goes to stdout and
diagnostics to stderr (see
[Diagnostics and exit codes](#diagnostics-and-exit-codes)), so redirecting one
never corrupts the other. File input is binary as well by default. Use
`--input-encoding hex` for hex text files or hex text on stdin;
`--input-encoding binary` explicitly selects binary input. Input encoding is
never guessed. `--hex` accepts case-insensitive contiguous hex bytes or
whitespace between complete byte pairs; prefixes such as `0x`, separators,
and incomplete pairs are rejected. An empty hex string or empty file is valid.
The same hex syntax applies to files and stdin, including CR/LF between pairs.
`--max-input-size` limits decoded bytes; hex whitespace is discarded as it is
read without buffering the encoded text. It does not limit the number of
whitespace characters read from a stream.

`formats` lists only enabled formats: `fixed`, `emv`, `ber`,
`der`, `bluetooth-ltv`, and `nfc-type2`. Existing library CMake component options control availability. Unknown
or disabled formats fail before reading input. No format detection is performed.

`--format fixed` defaults to one tag byte and one big-endian length byte, matching
`tlv_fixed_format_t{{1}, {1, TLV_BYTE_ORDER_BIG_ENDIAN}}`. `--fixed-tag-size N` (any positive
byte count), `--fixed-length-size N` (1 to 8) and `--fixed-byte-order big|little` configure it;
all three require `--format fixed` and are otherwise rejected as invalid usage. For example:

```sh
otlv dump --format fixed --fixed-tag-size 2 --fixed-length-size 1 --hex "0102 03 AABBCC"
otlv encode --format fixed --fixed-tag-size 2 --fixed-length-size 2 --fixed-byte-order little \
    --tag 0102 --value AABBCC
```

### Output

The tree example above prints:

```text
offset=0 tag=E1 length=3 value=5A0112
  offset=2 tag=5A length=1 value=12
```

Offsets are decimal, zero-based absolute positions of tags in the original
input. Tags and values are uppercase hexadecimal in wire order. Lengths are
decimal value byte counts. Constructed values include their encoded children.
Indefinite BER additionally prints `encoding=indefinite`; its resolved value
length and value exclude the enclosing EOC. EOC is never a separate element.

By default, `dump` prints top-level elements only. `--tree` prints nested
BER/DER elements with two spaces per level; other formats and `validate`
reject this option. Both dump modes still check nested BER/DER structure.
Output is deterministic text for inspection, not a versioned serialization
format. A malformed input may produce a partial dump before failure.

### Graphical trees and colors

`--pretty` implies `--tree` and prints UTF-8 branches (`├──`, `└──`, `│`)
instead of indentation alone. Top-level elements remain separate roots.
The original `--tree` layout remains available.

Tags are cyan when stdout is a supported terminal. Redirected output is
colorless by default. `NO_COLOR` (when present) and `TERM=dumb` disable
automatic color. `--force-color` emits ANSI sequences even when redirected
and overrides those environment settings; `--no-color` always disables color.
These two flags cannot be combined. Windows console mode and UTF-8 output
code page are temporarily configured as needed and restored after printing.

### EMV annotations

`dump --format ber --module emv` appends a readable name for each known tag.
`--describe` additionally prints the dictionary's value representation and
length bounds/step, for example:

```text
offset=0 tag=5A length=1 value=12 name="Primary Account Number (PAN)" description="Decimal digits; dictionary length: 1..10 bytes; step: 1"
```

Annotations use the built-in EMV Contact Book 3 v4.4 dictionary. Common
abbreviations have expanded display labels; other symbolic names are rendered
as words. Descriptions are type and length metadata, not a complete prose
explanation of every EMV data element or a copy of another parser's dictionary.
No value decoding, EMV length enforcement, or transaction validation is added
by these presentation options; raw values remain visible.

Known biometric containers select their specific dictionary contexts during
BER traversal. Unknown tags remain raw and are labelled unknown in the current
context; unknown containers do not cause their descendants to be guessed as
ordinary EMV tags. Primitive BER values remain opaque, including EMV elements
that describe embedded structures. A standalone context-specific fragment has
no enclosing context and begins in the base dictionary unless you select
another one with `--emv-context NAME` (see [EMV contexts](#emv-contexts)).

The EMV module must be compiled in. `--describe`, `--decode` and
`--emv-context` are accepted by `dump` and `decode` (and require
`--module emv`); `--output` and the color flags are dump-only.
`--module emv` itself is also accepted by `validate`, where it selects EMV
checks instead of annotating output (see below). EMV annotations and checks
both require BER, selected with `--format ber`; the wire format and the
module are separate options, so `--format der --module emv` is an error. Use `--format emv --module emv`
for definite EMV framing; `--format ber --module emv` retains general BER acceptance.

### Value decoding

`--decode` additionally decodes each known tag's value through the OpenTLV
codec layer (`tlv/codec/`) and appends it as `decoded="..."`, for example:

```text
offset=0 tag=9F02 length=6 value=000000001000 name="Amount, Authorised" decoded="1000"
```

The raw `value=` field is always present; decoding never replaces it. Only
tags with a dictionary entry and a registered codec are decoded - an unknown
tag, or a known tag whose value kind carries no codec (raw bytes, text, or a
template), is left with no `decoded` field and is not treated as an error. A
value that fails to decode (wrong length, invalid BCD, an undefined enum
value, and so on) instead reports `decode-error="..."`, drawn from the
codec's own diagnostic; the element itself is still printed, and the command
does not fail because of it.

Decoded output favors the codec's own C representation over further
interpretation: numeric fields (including currency amounts, which the codec
returns as unscaled minor units - see `tlv/builtins/emv/emv_codec.h`) print as a plain
decimal integer, bit flags print as hexadecimal, dates/times print as
`YYYY-MM-DD`/`HH:MM:SS` (the century of a date is assumed, as the dictionary
value itself does not carry one), and enumerated or composite kinds (account
type, cryptogram information, biometric type, AFL, CVM Results, Track 2) print
a short label or a compact field list. `--decode` cannot be combined with
`--pdol`, since a DOL entry carries a requested length, not a value.

### JSON output

`--output json` prints a single JSON document instead of the key=value text
above: a top-level object with an `elements` array, carrying the same
information under stable field names (`offset`, `tag`, `length`,
`indefinite` when true, `value`, `name`, `description`, `decoded`,
`decode_error`) and, for `--pdol`, (`offset`, `tag`, `requested_length`,
`name`). Fields that do not apply to an element (an unset `--describe`
description, an undecoded value, and so on) are simply omitted rather than
set to `null`. When `--tree` is set, a constructed BER/DER element carries
its children in its own nested `elements` array instead of a flat list, so
the document's shape mirrors the input's structure; without `--tree`, only
top-level elements appear and no element has an `elements` field.
`--pretty`'s graphical tree connectors are a text-mode presentation only and
have no effect on `--output json`. A malformed input may still produce a
document containing the elements parsed before the failure, matching the
partial-output-on-failure behavior described above; the diagnostic itself is
always reported separately, on stderr.

### JSON export

`decode` parses the input like `dump --tree` and prints it as the
[versioned JSON document](json-schema.md): tags and primitive values as
hexadecimal strings, constructed elements as nested `children` arrays, and for
BER an explicit `length_mode` of `definite` or `indefinite`:

```sh
otlv decode --format ber --hex "E1 05 5A 01 12 5A 00 30 80 04 01 AA 00 00"
```

```json
{"schema":"opentlv.tlv","version":1,"format":"ber","elements":[{"tag":"E1","length_mode":"definite","children":[{"tag":"5A","value":"12"},{"tag":"5A","value":""}]},{"tag":"30","length_mode":"indefinite","children":[{"tag":"04","value":"AA"}]}]}
```

`decode` takes the input, limit and module options of `dump` (`--format`,
`--input`/`--hex`, `--input-encoding`, `--max-*`, `--module emv`,
`--describe`, `--decode`, `--emv-context`, `--recover`) and rejects the text
presentation options (`--tree`, `--pretty`, colors, `--output`, `--pdol`).
The whole input is always parsed as a tree, so BER and DER nesting is followed
up to `--max-depth`. A failed export prints nothing on stdout, unlike `dump`,
so a partial document is never mistaken for a complete one. With
`--module emv` each known element carries its dictionary `name`; unknown tags
carry only their raw `tag` and `value`.

Offsets are not part of the document. Use `dump --output json` when you need
them.

### Encoding

`encode` writes TLV data with the OpenTLV writer for the format chosen by
`--format`, so the format alone determines the tag and length encoding. It has
two input modes: one element from `--tag`/`--value`, or a whole
[JSON document](json-schema.md) from `--input`.

```sh
otlv encode --format ber --tag 9F02 --value 000000001000
otlv encode --format ber --input elements.json
otlv encode --format ber --input - --output-encoding binary --output-file out.bin
```

```text
9F0206000000001000
```

For a single element, `--format` and `--tag` are required; `--value` is
optional and defaults to an empty value. `--tag` and `--value` use the same hex
syntax as `--hex` (case-insensitive, complete byte pairs, optional whitespace
between pairs). `--value` is limited by `--max-input-size`; a tag longer than
8 bytes, the longest tag any built-in format accepts, is rejected.

`--input PATH` reads a JSON document instead (`-` for stdin, read as bytes on
Windows too); it cannot be combined with `--tag` or `--value`. Omitting both
`--tag` and `--input` reads the JSON document from stdin as well, the same as
`--input -`. Every length is
derived while encoding, children are written inside their parent, and BER
elements marked `"length_mode":"indefinite"` get the `80` length and the
end-of-contents octets. Before anything is printed the encoded bytes are read
back with the format's reader and checked like `otlv validate` does, so the
output is always accepted by the library reader and structural validator.
`--max-input-size` limits the JSON text and the encoded bytes, `--max-depth`
the nesting of `children` and `--max-elements` the number of elements. Nothing
about the JSON is guessed: a document that does not follow the
[schema](json-schema.md), names another format than `--format`, or needs a
representation the format lacks (children under `default`, indefinite length
under `der`) is rejected. The round trip `decode` then `encode` preserves
element structure and raw primitive values but not the exact bytes of length
fields; see [Round trip](json-schema.md#round-trip).

Output is uppercase hex followed by a newline by default;
`--output-encoding binary` writes the raw encoded bytes with no newline,
including on Windows. `--output-file PATH` writes the result to a file instead
of stdout, and only after the whole document was accepted, so a rejected
document leaves no file behind. Either encoding can be read back with
`otlv dump` (`--input -`, plus `--input-encoding hex` for the hex form).

Nothing is printed for a rejected input. Malformed hex, an invalid JSON
document, unknown or disabled formats, and options `encode` does not take exit
with code 2; `encode` takes `--format`, `--tag`, `--value`, `--input`,
`--output-encoding`, `--output-file`, `--max-input-size`, `--max-depth` and
`--max-elements`. An element the writer rejects (an invalid BER tag, or a value
too long for `fixed`) reports `otlv: cannot encode element N: <reason>`
and exits with code 1; N counts elements from zero in document order. Exceeded
limits and unreadable or unwritable files exit with code 3.

### Path queries

`query` prints the elements addressed by a path of hexadecimal tags, so a
script can read one value from nested data without post-processing the whole
dump. The path is a positional argument and the input options are the same as
for `dump`.

```sh
otlv query 6F/A5/50 --format ber --input card.bin
otlv query 6F/A5/50 --format ber --input card.bin --value
otlv query 6F/A5/50 --format ber --input card.bin --output json
```

```text
offset=8 tag=50 length=2 value=4142
```

`6F/A5/50` means a top-level `6F`, its direct child `A5` and that element's
direct child `50`. Every element reached this way is printed in document
order; a tag that occurs several times can therefore produce several lines.
Tags are hex in either case, separated by one `/`; spaces, empty steps and a
leading or trailing `/` are usage errors. This first version supports exact tag
paths only, with no wildcards, indexes or recursive search. The syntax and
matching come from the library ([Path queries](https://github.com/OpenTLV/opentlv/blob/edebe957ee2a1e0bf5685c3bd55a33788446e80d/docs/guides/queries.md)), not
from the CLI.

- Text output is one line per match in the format of `dump`, without nesting.
- `--value` prints only the value bytes of each match as one line of hex, an
  empty line for an empty value.
- `--output json` prints `{"matches":[...]}`; each match has `path`, `offset`,
  `tag`, `length` and `value`. It cannot be combined with `--value`.
- A path of more than one tag needs `--format ber` or `--format der`, the
  formats that have nested values; other formats accept one-tag paths.
- The whole input is still parsed, so damaged data after a match fails the
  command with exit code 1, and `--max-depth`, `--max-elements` and
  `--max-input-size` apply as for `dump`.
- No match is reported as `otlv: no match for query ...` with exit code 5, so a
  script can tell a missing element from invalid data.

### Full compiled Query and semantic diff

Full expressions can be positional or supplied with `--query`. Existing exact
paths preserve their text/JSON/`--value` behavior; descendants (`//`), predicates,
sets, typed variables and scalar expressions use the compiled C Query engine
through the C++ program/execution facade.

```sh
otlv query --query 'count(//50)' --format ber --input capture.bin
otlv query --query '//50[value(.) = $wanted]' --var wanted:bytes=4142 --format ber --input capture.bin
otlv query --query '//50[num(.) > $min]' --var min:int=100 --format ber --input capture.bin --explain
otlv query '//51' --exists --format ber --input capture.bin
otlv diff --format ber --input left.bin --against right.bin --where '//70/5A' --output json
```

Variable declarations use `NAME:int=DECIMAL`, `NAME:bytes=HEX` (even-length hex,
including empty) or `NAME:string=UTF8`. The shell must preserve literal dollar
signs; single-quoted examples work in Bash and PowerShell. Variables are bound
through native slots, never substituted into Query text. `num` uses the generic
minimal signed big-endian integer provider; `bcd` uses packed decimal, and `text`
uses UTF-8. Symbolic EMV resolution is enabled with `--format emv`.

`--count` and `--exists` wrap a node expression into a scalar expression. False
and zero return exit code 0, as does every successful scalar. Empty node results
return 5. Full Query compilation/binding/backend failures return 2 and execution
failures return 3; existing V1 input parse failures retain exit code 1. Scalar
JSON is `{ "type": native_result_kind, "value": value }`, with integer JSON
numbers, booleans, uppercase hex bytes and UTF-8 strings. `--value` is only for
node selections and cannot be combined with JSON.

`--backend streaming` always uses retained canonical Tree events with explicit
`--max-elements` capacity and rejects D before traversal. It never builds a
Document. `--backend document` selects owning Document materialization explicitly.
`auto` chooses retained streaming for S0-S2 and materializes D. Input is already
owned by the CLI; retained payloads borrow that input. The owning C++ convenience
and CLI allocate program/workspace/result storage; the C engine does not allocate.
The Document backend retains input coordinates, so its matches report the same
source offsets as streaming and `@offset`/`@hlen` are available in both.

`--explain` writes JSON to stderr with normalized Query, language/result/level,
chosen backend, program/scratch sizing and alignment, capacities, work budget,
validation policy and an explicitly unstable internal logical IR. It does not
change the normal result output. Full execution drains to structural EOF; Schema
or DER semantic validation is not implied. Human/compact/json diagnostics retain
native Query byte spans and available resource/source context.

`diff` requires two files and the Document component. Its selector is compiled
once and evaluated on each original complete input. It reports added, removed
and changed direct nodes; zero differences succeeds with an empty result. Node
correspondence uses ancestor tags and same-tag sibling occurrence, independent
of byte offsets. A node selected on either side includes its counterpart. Selected
ancestors do not implicitly include excluded descendants. Repeated-tag insertions
may shift correspondence. JSON contains a `changes` array with kind, correspondence
path and original left/right primitive content/classification; absent sides and
constructed Values are `null`. This minimal surface does not bind typed variables
or provider environments for diff. See [Query integration contracts](https://github.com/OpenTLV/opentlv/blob/edebe957ee2a1e0bf5685c3bd55a33788446e80d/docs/guides/queries.md#full-programs-and-integration).

### Tag lookup

`tag` looks up one BER tag in the OpenTLV EMV dictionary, so the CLI can serve
as a quick tag reference. The metadata comes from the native EMV definitions
(`tlv_emv_find` in the base context); the CLI keeps no dictionary of its own.

```sh
otlv tag 9F02 --module emv
```

```text
Tag:         9F02
Name:        Amount Authorised
Type:        Numeric value (binary or decimal BCD, tag-dependent)
Form:        Primitive
Length:      6
```

The tag is a positional argument in the same hex syntax as `--hex`, and must
be exactly one complete BER tag. `--module emv` is required. `Length step` is
printed only when the dictionary's permitted lengths advance by more than one
byte (for example the AFL). `--output json` prints one object with `tag`,
`module`, `known` and, for known tags, `name`, `symbol`, `type`,
`constructed`, `min_length`, `max_length` (omitted when unbounded) and
`length_step`.

A tag with no dictionary entry is a valid result, not malformed data: text
output prints `Result:      Unknown tag in the EMV module (base context)`,
JSON output has `"known":false`, and the exit code is 0. An invalid or
incomplete tag, an unknown module, or any option other than `--module` and
`--output` exits with code 2.

`tags` lists every tag in the dictionary (base context), sorted by tag, when
you do not know which tag to look up:

```sh
otlv tags --module emv --search amount
```

```text
81      Amount Authorised Binary
9F02    Amount Authorised
9F03    Amount Other
...
```

`--search TEXT` keeps only tags whose displayed name contains `TEXT`
(case-insensitive). `--output json` prints `{"module":"emv","tags":[...]}`
where each element has the same fields as a known `tag` result. A search with
no matches is not an error: it prints nothing (or an empty array) and exits 0.
`tags` accepts only `--module`, `--output` and `--search`; `--search` is
rejected by every other command.

### PDOL / DOL inspection

Use `--pdol` to read a raw PDOL value as ordered tag/length pairs:

```sh
otlv dump --format ber --pdol --hex "9F02069F1A02" --module emv
otlv validate --format ber --pdol --input pdol.hex --input-encoding hex
```

Without annotations, the output is:

```text
offset=0 tag=9F02 requested-length=6
offset=3 tag=9F1A requested-length=2
```

Supply the contents of tag `9F38`, not its enclosing TLV header. Ordinary TLV
dumping still leaves that value opaque. The same pair representation is used by other
EMV DOLs. Tags contain one or two bytes; each requested length is exactly one
unsigned byte (0..255), including `80` and `FF`. No value follows the length.
Order and duplicate tags are preserved. This mode neither constructs terminal
response data nor checks whether the requested lengths match dictionary bounds.

All existing input sources, decoded-input and element-count limits apply.
Empty input succeeds. Missing lengths, malformed tags, and tags longer than
two bytes fail with offsets. `--tree` and `--pretty` are rejected because a DOL
is flat; `--max-depth` has no effect. BER must be enabled; the EMV dictionary
is needed only for optional `--module emv` annotations.

### EMV schema validation

`validate --format ber --module emv` additionally checks the parsed input
against `tlv_emv_structure_schema` (see
[EMV structural validation](https://github.com/OpenTLV/opentlv/blob/edebe957ee2a1e0bf5685c3bd55a33788446e80d/docs/standards/emv/README.md#structural-validation)):
mandatory tags, forbidden/unknown tags, duplicate tags, length bounds, and
required nesting for the FCI Template, Application Template, and GPO
Response Message Template Format 2. It runs only after the input has parsed
as valid BER, only for `validate` (`dump --module emv` only annotates
tags), and not with `--pdol` (a DOL's tag/length pairs are not a TLV
structure to check against a schema).
A schema violation is reported like any other failure, but prefixed with
`schema` to keep it distinguishable from a format/framing error. A missing
mandatory tag uses `TLV_ERR_SCHEMA` with `missing` detail. The reported Tag
comes from the Schema, and its byte position is the enclosing scope end.

```console
$ otlv validate --format ber --module emv --hex "6F00"
otlv: schema TLV_ERR_SCHEMA at byte 2 tag=84: schema constraint violated
```

The exit code contract is unchanged (1 for a schema violation, 3 for an
exceeded limit). Unmodeled top-level tags, such as the Read Record Template,
are accepted unchecked; this is not a full EMV transaction or value validator.

### EMV checks

`validate --module emv` runs the checks chosen by `--emv-check`, always on
input that has already parsed as valid BER:

| `--emv-check` | Checks | `compact` prefix |
| --- | --- | --- |
| `structure` (default) | The structural schema above. | `schema` |
| `dictionary` | Every element whose tag is in the EMV dictionary, in the context it appears in, has a length the dictionary permits (its bounds and length step). | `dictionary` |
| `all` | `structure`, then `dictionary`; the first failure is reported. | either |

The `compact` prefix distinguishes the two checks on one line; `human` and
`json` do the same with structured detail instead: a structural violation
carries a `path` and, for most kinds, a `field` name, while a dictionary
violation carries a `dictionary` `stage`.

The dictionary check uses the same lookup and contexts as `dump --module emv`
and the library's `tlv_emv_validate_length`. It reports the first offending
element, labeled `dictionary`, with exit code 1; see
[Diagnostics and exit codes](#diagnostics-and-exit-codes) for the `--diagnostics`
renderers. In `compact` form:

```sh
$ otlv validate --format ber --module emv --emv-check dictionary --hex "9F02050000000010" --diagnostics compact
otlv: dictionary TLV_ERR_INVALID_LENGTH at byte 0 tag=9F02: invalid length encoding
```

What runs, and what does not:

- Tags with no dictionary entry in their context are **not** errors; they are
  preserved and left unchecked. The dictionary check does not require a tag to
  be known, does not check that mandatory tags are present outside the
  templates the structural schema models, and does not decode or check values
  (BCD digits, dates, enumerations); `--decode` shows those diagnostics
  without failing.
- Children of a container are looked up in that container's context, and
  containers the dictionary does not know contribute no context, so their
  children are unchecked (as they are labelled unknown by `dump`).
- Neither check is an EMV kernel, transaction, or cryptographic validation,
  and cross-tag rules (for example that a tag must agree with another) are out
  of scope.
- `--emv-check` applies to `validate` only, and not with `--pdol`.

### EMV contexts

The dictionary is context dependent: the same tag can mean different things
inside different templates (for example `82` is the 2-byte Application
Interchange Profile at the top level but a 1-byte Biometric Subtype inside a
Biometric Header Template). During a traversal the CLI switches context on known
containers such as the Biometric Information Template `7F60`. A fragment cut
out of such a container has no enclosing element to say which context applies,
so select it explicitly with `--emv-context NAME`, for `dump`, `decode` and
`validate --emv-check dictionary`:

| Name | Context |
| --- | --- |
| `base` (default) | Ordinary application data. |
| `bit` | Inside `7F60` (Biometric Information Template). |
| `bht` | Inside `A1` within `7F60` (Biometric Header Template). |
| `bht-format` | Inside a level-2 `A1`/`A2` within the BHT. |
| `bit-group` | Inside `BF4A`/`BF4B` or a terminal group. |
| `biometric-counters` | Inside `BF4C`. |
| `biometric-attempts` | Inside `BF4D`. |
| `biometric-verification` | Inside `BF4E`. |

```sh
otlv dump --format ber --module emv --emv-context bht --hex "820101"
otlv validate --format ber --module emv --emv-check dictionary --emv-context bht --hex "82020101"
```

The first prints the element as `Biometric Subtype`; the second fails because
`82` is 1 byte in that context. Contexts never fall back to the base
dictionary. The structural schema models base-context templates only, so
`--emv-check structure` (and `all`) require the base context; use
`--emv-check dictionary` with any other. `--emv-context` requires
`--module emv` and cannot be combined with `--pdol`.

### Recovery scanning

`dump` and `decode` stop at the first damaged byte by default. With
`--recover` they instead resynchronize and keep going. This CLI-owned recovery
policy uses the public single-element `tlv_read()` API: when the element at the
current offset cannot be read, or its contents are malformed, it checks each following
offset for the next plausible element, and the bytes in between are skipped.

```sh
$ otlv dump --format ber --hex "5A0112 0000 5A0134" --recover
offset=0 tag=5A length=1 value=12
skipped offset=3 length=2 error=TLV_ERR_INVALID_TAG error-location=input:point:3
offset=5 tag=5A length=1 value=34
otlv: skipped 2 byte(s) at offset 3: TLV_ERR_INVALID_TAG at byte 3: invalid tag
otlv: output is incomplete: recovery skipped 1 range(s), 2 byte(s) in total
$ echo $?
4
```

- **Skipped ranges** are reported where they occur (`skipped offset= length=
  error= error-location=` lines in `dump` text output), and again on stderr with
  a summary. `error` and `error-location` describe the first failure that made
  the range unreadable, with the same location as its stderr diagnostic:
  `domain:kind:begin`, `domain:kind:begin..end` for a span, or
  `unknown:unknown` when the failure has no location. The location can lie
  inside or after the range.
- **Incomplete output.** In `--output json` and in `decode`, the document
  gains `"complete":false` and a `"skipped"` array of objects with `offset`,
  `length`, `error`, `location` and `message`. `location` has the `domain` and
  `kind` of the failure and, when known, its `begin` and `end`, like the
  `location` of a JSON diagnostic. An undamaged input under
  `--recover` reports `"complete":true` and an empty array. A recovered
  `decode` document is incomplete and is rejected by `encode`.
- **Exit status 4** means recovery skipped data, so the output is incomplete;
  it is distinct from 1 (strict failure). Without `--recover`, or when nothing
  was skipped, the exit codes are unchanged.
- **Offsets** are absolute positions in the input. A recovered element is
  always reported as a top-level element, even when the scanner found it inside
  a damaged constructed element.
- **Limits are not damage.** `--max-input-size`, `--max-depth` and
  `--max-elements` still fail the run with exit code 3, and `--max-elements`
  counts only the elements that were output.
- **Heuristic.** The scanner accepts what looks like a well-formed element
  (syntactic checks only, no dictionary or schema), so a match is not proof of
  an original element boundary; damaged bytes can be mistaken for an element,
  and an element inside a skipped range can be output where a byte-level
  decoder would have skipped it. Treat recovered output as evidence for
  inspection, not as a repaired copy.
- `validate` stays strict and rejects `--recover`, as do `--pdol` and `encode`.
  It is the only command whose exit status certifies that the input is valid.

### Validation and limits

`validate` is silent on success. Both commands consume all concatenated
elements; empty input succeeds and invalid trailing bytes fail. Default,
fixed and bluetooth-ltv values are opaque unless a semantic module is selected.
BER uses constructed-tag recognition; DER uses
the existing structural validator. This does not provide full ASN.1 value
validation or canonical SET/SET OF ordering; EMV structural
validation is available via `--module emv`, above. Bluetooth schema and codec
validation is available via [`--module bluetooth`](#bluetooth-semantic-inspection).

| Option | Default | Meaning |
| --- | --- | --- |
| `--max-input-size N` | 16777216 | Maximum decoded input bytes (16 MiB) |
| `--max-depth N` | 64 | Maximum descendant depth; top-level depth is zero |
| `--max-elements N` | 100000 | Maximum visited elements, including hidden descendants |

Limits are inclusive nonnegative decimal integers fitting native `size_t`.
Depth is restricted to 0..64. Zero is a real limit, not an unlimited setting.
Traversal follows library depth semantics: empty constructed values require
no descent. BER indefinite-length resolution also has the library's fixed
64-scope bound. The input is buffered in CLI-owned memory; this does not change
the allocation-free library core. Limits constrain accepted input and traversal;
they are not a wall-clock timeout or incremental streaming interface.

## Shell completion

```sh
otlv completion bash > ~/.local/share/bash-completion/completions/otlv
otlv completion zsh > "${fpath[1]}/_otlv"
otlv completion fish > ~/.config/fish/completions/otlv.fish
otlv completion powershell >> $PROFILE
```

`completion` prints a completion script for `bash`, `zsh`, `fish` or
`powershell` to stdout; install it as shown above (once per shell, or on
every prompt for bash/zsh, per that shell's own completion conventions) and
restart the shell. The script completes top-level commands, each command's
own options, and known option values (`--format`, `--output`, `--emv-context`
and so on) from the same tables `otlv` itself uses, so it reflects this
build: only formats enabled at compile time, and EMV/`--format fixed` options
only when those are compiled in. Free-form arguments (`--hex`, `query`'s
path, `tag`'s hex) and file arguments (`--input`, `--output-file`) fall back
to the shell's own file completion where applicable.

## Diagnostics and exit codes

Command output goes to stdout; diagnostics go to stderr. `--diagnostics NAME`
selects how a failure is rendered: `human` (the default), `compact`, or
`json`. All three describe the same underlying detail, collected
independently of how it is presented: the symbolic `TLV_ERR_*` code, a
description, a byte offset, the affected tag when known, and, for a failure
inside a constructed element, the hierarchical path of tags enclosing it
(`dump`, `validate`, `decode` and `query` all track this, not just `dump`).
Offsets do not promise the exact corrupted byte.

`human` prints one field per line:

```sh
$ otlv validate --format ber --module emv --hex "6F048402AABB"
otlv: error: invalid length encoding

code: TLV_ERR_INVALID_LENGTH
offset: 0x2 (2)
path: 6F
tag: 84
field: df_name
expected length: 5..16
actual length: 2
```

`compact` prints the same detail on one line: this is the CLI's original
wording (`otlv: schema TLV_ERR_INVALID_LENGTH at byte 2 tag=84: invalid
length encoding` for the example above), kept for scripts that scrape
stderr. `json` prints a single-line JSON object with the same fields
(`code`, `message`, `offset`, `tag`, `path`, `field`, and so on), for
scripts that would otherwise have to reparse the human or compact text; a
`--recover` run additionally wraps each skipped range's diagnostic with the
`skipped_offset`/`skipped_length` of the range it recovered from.

A plain wire-level failure (no `--module emv`) additionally reports which
step failed (`tag`, `length`, `value` or `trailer`) and, for a value or
trailer that does not fit, the declared length versus the bytes actually
available:

```sh
$ otlv validate --format ber --hex "0402AA"
otlv: error: truncated input

code: TLV_ERR_TRUNCATED
offset: 0x2 (2)
tag: 04
while reading: value
declared length: 2
available: 1
```

This declared-length/available detail comes from re-reading the failing
element on its own once the traversal has located it, bounded to the value it
actually sits in (not necessarily the whole input); it is shown whenever
that re-read reproduces the original failure exactly. BER and DER's
constructed-length handling does not currently surface it back through this
path, so a BER/DER value-length overrun shows the step, offset, tag and
path, but not the two length lines above; every other format does.

An EMV schema violation (`validate --module emv`) additionally carries the
schema field name and the expected-versus-actual detail for the violated
rule (occurrence counts, length bounds, or a primitive/constructed
mismatch), computed directly by the schema check, so it is unaffected by
that BER limitation. A dictionary-length violation (`--emv-check
dictionary`) is labeled `dictionary` (see [EMV checks](#emv-checks)) and
similarly reports the permitted-versus-actual length and the dictionary
field name. Missing mandatory tags use `TLV_ERR_SCHEMA` with `missing`
detail, the absent tag from the schema, and the enclosing scope end. JSON's
`anchor` identifies this boundary (`2`), separately from an existing element
(`1`), insertion point (`3`) or unknown position (`0`).

Formatting is presentation only, layered on top of the library's structured
diagnostics; see [Diagnostics](https://github.com/OpenTLV/opentlv/blob/edebe957ee2a1e0bf5685c3bd55a33788446e80d/docs/guides/diagnostics.md) for the underlying
model.

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Invalid TLV data, or an element `encode` cannot write |
| 2 | Invalid command, option, hex input, JSON document, or unavailable format |
| 3 | I/O failure, allocation failure, or exceeded resource limit |
| 4 | `--recover` skipped damaged data: the output is incomplete |
| 5 | `query` matched no element |

Automatic format detection, custom text input syntax, full ASN.1 value
validation, EMV kernel behavior, and prebuilt release binaries are outside the
scope of the CLI.

## Bluetooth semantic inspection

With `OPENTLV_BLUETOOTH=ON`, `--module bluetooth` adds AD Type names from the
public Definition registry to `dump` and `decode`. Add `--decode` to render
Flags, Local Names, Tx Power, 16/32/128-bit UUID lists, Service Data and
Manufacturer Specific Data through the public value codecs:

```sh
otlv dump --format bluetooth-ltv --module bluetooth --decode --hex "020106020AFC0000"
otlv validate --format bluetooth-ltv --module bluetooth --hex "020106020AFC0000"
```

The dump includes:

```text
offset=0 tag=01 length=1 value=06 name="Flags" decoded="0x06"
offset=3 tag=0A length=1 value=FC name="Tx Power Level" decoded="-4 dBm"
```

The module accepts trailing zero padding using the public AD container API.
Only significant structures are traversed; their offsets still refer to the
original input. Embedded zeros remain value bytes. A nonzero byte after
padding begins is an error. Without `--module bluetooth`, `bluetooth-ltv`
remains strict wire inspection, including rejection of zero-length structures.

`validate --module bluetooth` checks the public AD schema first, then the
supported value codecs. Schema and codec failures retain original offsets and
raw AD Types in the selected diagnostic format. Unknown AD Types and Company
Identifiers are accepted. Company names are annotations from the bundled,
non-exhaustive registry; service and manufacturer payloads remain opaque hex.

`dump` and `decode` annotate malformed known values with `decode_error`
(`decode-error` in text) without failing wire inspection. Use `validate` for
semantic validity. Text output escapes Local Name control characters and
quotes. `--output json` on `dump` retains `offset`, `tag`, `length` and `value`
and adds `name` and optional `decoded` or `decode_error` strings.

`decode` exports the significant structures using the existing versioned JSON
schema. Re-encoding preserves those structures but does not restore container
padding. `--recover` is unsupported with this module; `--describe` and EMV
options require the EMV module.

## Generate reproducible wire corpora

```sh
otlv generate --format ber --seed 42 --count 10000 --output-dir build/property-data/ber
```

`--format`, `--seed`, `--count` and `--output-dir` are required. Seed accepts
an unsigned 64-bit decimal integer, including zero. Count must be positive and
always means complete cases (files in the selected encoding), rather than elements. Case indices start at
zero; names are decimal with at least six digits (`000000.bin`, `000001.bin`,
and so on). Generation does not read stdin and is silent on success.

Each case represents an independently round-trippable complete TLV stream.
The native generator selects the number of elements and nesting per case.
The same native generator algorithm version, CLI candidate domain, Format/configuration,
limits, seed and case index reproduce identical bytes independently of call order.
Retain those settings and the OpenTLV version with a corpus; upgrading can change
its candidate domain or generator algorithm.

Limits are `--max-elements` (default 32, including parents), `--max-depth`
(default 4, roots at zero, at most 64), `--max-value-size` (default 256 bytes)
and `--max-case-size` (default 4096 bytes). Elements and case size must be positive;
Value size and depth may be zero. Nested formats use the requested depth; flat
formats use zero. Scratch storage is `(effective depth + 1) * max-case-size` bytes,
plus the owned case result. Cases are generated and written sequentially.

| Format | Ordered candidate tags | Value domain |
| --- | --- | --- |
| `ber`, `der`, `emv` | `04`, `80`, `30`, `A0` | Primitive arbitrary bytes; constructed child streams |
| `fixed` | Identifier of configured width, every byte `01` | Capped to the configured Length capacity |
| `bluetooth-ltv` | `09`, `FF` | Capped to 254 bytes |
| `nfc-type2` | `03`, `FD` | Capped to 65534 bytes; excludes NULL and Terminator |

Fixed accepts the existing `--fixed-tag-size`, `--fixed-length-size` and
`--fixed-byte-order` options. Optional formats must be enabled in the build.
These are wire corpora: they do not promise Schema, Codec, EMV application,
Bluetooth AD or NDEF semantic validity. No property runner is required.

Missing directories are created. Existing target case files are rejected before
writing any case, and each file is created exclusively. Unrelated directory
contents are retained. A later generation or I/O failure leaves earlier completed
files available and reports the failing case; a failed write removes its partial
file. Use a fresh directory when retrying. Invalid usage/configuration returns 2;
generation failure or I/O/resource failure returns 3. Unsupported formats and
impossible limits produce a clear diagnostic.

Choose `--output-encoding bin|json`. The default is `bin`; explicit `bin`
behaves identically. Binary mode writes only `000000.bin`, `000001.bin`, etc.
JSON mode writes only `000000.json`, `000001.json`, etc.; no binary files are
written. Each JSON file uses the existing versioned model from `otlv decode`,
including raw primitive Values, constructed children and BER length modes.
Use `otlv encode --input` with the same Format/configuration to reconstruct the
corresponding wire case. Both output modes use the same native generated bytes;
JSON is decoded and serialized entirely within the CLI. Neither the native C
generator nor its tlv++ wrapper depends on JSON or nlohmann/json.

Collision checks apply only to paths of the selected encoding; unrelated files,
including those in the other encoding, are retained. Failed writes remove their
partial file; earlier complete cases remain available.

## Documentation origin

This guide and the [JSON schema](json-schema.md) were migrated from
[Core's CLI documentation](https://github.com/OpenTLV/opentlv/tree/edebe957ee2a1e0bf5685c3bd55a33788446e80d/docs/cli).
Build instructions and repository links now refer to the standalone CLI;
command and JSON behavior remain governed by the migration baseline.
