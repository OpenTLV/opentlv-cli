# CLI migration regression baseline

This is the frozen behavior reference for extracting `otlv` from Core (#621,
parent #619). It supplements the existing tests without changing CLI behavior.
Run the same inputs against the original and standalone executables, then compare
exit status, stdout, stderr and files. A successful build alone is insufficient.

## Origin and scope

| Identity | Recorded value |
| --- | --- |
| Repository | `https://github.com/OpenTLV/opentlv` |
| Originating Core commit | `e9cbb29897652fa75753ea89459e3f5e26671d3a` |
| Nearest preceding release tag | `0.7.1` |
| Tag commit | `e12a52ff69a64468eecab084795a0530c273efea` |
| Distance from tag | 11 commits; the baseline is from the origin SHA, not the tag |
| Reference capture | Windows x64, MSVC, Release, C++11, static Core, default capabilities/formats |

`expected.json` records the executable SHA-256, compiler version and CMake
configuration from a clean detached checkout of the origin SHA. `cases.json`
records the origin, SHA-256 of original Git blobs used as source material, and
all invocation arguments, stdin bytes and input files. Its logical JSON hash
binds the snapshot to the exact case inventory. Inputs are embedded as hex so
the suite can be copied to another repository without resolving Core paths.

There are 154 representative cases. All commands, all six CLI formats, return
codes 0 through 5, three diagnostic renderers, binary/text input, stdin, file
output, partial output, recovery, Query, semantic modules and generation are
represented. The original suites below remain required for their broader edge
coverage. This snapshot is not an exhaustive enumeration of every argument
combination or a replacement for native Core contracts.

## Existing regression tests and fixture inventory

Paths in this section are relative to the Core repository root at the origin.

| Test / registration | Existing coverage | Owner after extraction |
| --- | --- | --- |
| `tools/cli/test.cmake` / `Integration_cli` | Argument rejection, feature-gated formats/options/completions, input streams, resource/I/O failures, colors, text/JSON, encode/decode, Query/diff, diagnostics, EMV/Bluetooth semantics, recovery, deep nesting and generator files/replay/no-overwrite | CLI; preserve the suite and its assertions |
| `tools/cli/examples.cmake` / `Integration_cli_cpp_examples` | CLI equivalents of the native C++ parsing, writing, Query and JSON examples | CLI adapter checks; native C++ examples stay in Core |
| `tests/query/cli_facade.py` / `query-cli-conformance` | Shared Query corpus through CLI auto/Document backends, variables, scalar/node results and diagnostic locations; explicit exclusions for external fixture name resolution | CLI runner; consume a pinned copy of the shared corpus |
| `tests/property/` / `Property_*` | Deterministic generated-wire round trips and failure evidence; now directly calls the Core Generator API | Core; no dependency on `otlv` or the C++ facade |
| `tests/query/` native/C++ runners, reference evaluator and non-CLI facade runners | Query semantics, plans, adversarial inputs, differential properties and language contracts | Core / respective bindings |
| Native unit/integration tests, fuzz targets and `examples/tlv*` | Reader, Writer, Generator, Document, Format, Schema, Codec and C/C++ API contracts | Core |
| `tools/cli/baseline/` / `Integration_cli_baseline`, `Integration_cli_baseline_runner` | Frozen process/file observations and comparator integrity | CLI; copy this directory unchanged for migration comparison |

The CLI tests are registered in `tools/cli/CMakeLists.txt` under
`OPENTLV_BUILD_CLI_TESTS`. `Integration_cli` requires only CMake; the examples
require BER. Query CLI conformance requires Python, BER, Query frontend and
Document. The baseline requires Python 3.8+ and all six CLI formats, Query
frontend and Document. Reduced builds retain the capability-aware original
suite; they do not silently run a partial frozen snapshot.

Existing GCC/Clang build workflows run the `integration` label and MSVC runs
CTest, so the new baseline registration participates in those jobs when its
prerequisites are available. Run `query-cli-conformance` explicitly as well:
its historical labels are `query;conformance;memcheck-full`, not `integration`.

| Fixture / source | Purpose and retention |
| --- | --- |
| `tools/cli/input.bin` | Binary stdin/file sentinel containing LF, CR, Ctrl-Z and a high byte; CLI-owned |
| Literals and generated files in `tools/cli/test.cmake` | Valid/invalid hex and JSON, `cli-hex.txt`, encode/JSON round trips, diff pairs, nested/recovery/diagnostic inputs, Bluetooth/EMV JSON, bounded generator corpora and collision sentinels; preserve the generating script, not transient build files |
| Literals and `cpp-example.json` in `tools/cli/examples.cmake` | Fixed greeting and nested BER/Query example; CLI-owned acceptance fixtures |
| `examples/nfc/type2/{sample,empty-ndef,controls,short-254,extended-255,extended-256,framing-policy}.bin` | Shared protocol examples; Core owns originals, CLI retains immutable migration copies |
| `examples/nfc/type2/invalid/{missing-length,truncated-extended,truncated-value,nonminimal-extended,reserved-length}.bin` | Shared malformed NFC fixtures; same ownership as valid examples |
| `tests/query/corpus.json` | Shared language/diagnostic expectations; Core owns the corpus, CLI consumes a versioned snapshot without moving native runners |
| `docs/cli/README.md`, `docs/cli/json-schema.md` | CLI usage and versioned JSON model; CLI documentation ownership after extraction |
| `cases.json`, `expected.json` here | Portable frozen copies of representative inputs and exact observations; source blob hashes retain their provenance |

Keep CLI-specific process/formatting checks separate from shared semantic
fixtures. Do not move native Core tests just because the CLI consumes the same
API. The CLI `generate` command's argument parsing, JSON/file handling and
no-overwrite tests remain CLI-owned; generator algorithm and deterministic wire
properties belong to Core. The CLI command itself is unchanged in this issue.

## Commands and arguments

The complete originating `--help` and four shell completion scripts are frozen
in `expected.json`. Their per-command option lists complement the usage and
constraints in [the CLI manual](../../../docs/cli/README.md) and
[JSON schema](../../../docs/cli/json-schema.md). The parser's option masks and
additional validation in `tools/cli/src/options.cpp` remain authoritative.

| Entry point | Arguments and purpose |
| --- | --- |
| `--help`, `--version`, `formats` | Single-argument entry points: usage, library version and enabled format names |
| `completion SHELL` | Exactly one of `bash`, `zsh`, `fish`, `powershell`; script written to stdout |
| `dump` | Explicit format and input; text/JSON inspection, `--tree`, `--pretty`, `--force-color`, `--no-color`, module annotations and `--recover` |
| `validate` | Explicit format and input; structural validation, optional semantic module/EMV checks and diagnostics |
| `decode` | Explicit format and input; versioned JSON export, optional annotations/decoding/recovery |
| `encode` | `--format`, either `--tag HEX [--value HEX]` or JSON `--input PATH\|-`/stdin; `--output-encoding hex\|binary`, `--output-file PATH` |
| `generate` | Required `--format`, `--seed UINT64`, `--count N`, `--output-dir PATH`; `--output-encoding bin\|json`, `--max-value-size`, `--max-case-size`, depth/element limits |
| `query` | Positional tag path or `--query EXPR`; `--var NAME:TYPE=VALUE`, `--count`, `--exists`, `--value`, `--backend auto\|streaming\|document`, `--explain`, text/JSON output |
| `diff` | `--format`, `--input LEFT`, `--against RIGHT`, optional `--where EXPR`, text/JSON output; requires Document |
| `tag HEX` | Required `--module emv`; text/JSON dictionary entry, unknown tags are successful results |
| `tags` | Required `--module emv`; optional case-insensitive `--search TEXT`, text/JSON listing |

Shared option families (only accepted on the commands documented in the manual):

| Family | Options / values |
| --- | --- |
| Input | `--format fixed\|ber\|der\|emv\|bluetooth-ltv\|nfc-type2`, `--input PATH\|-`, `--hex BYTES`, `--input-encoding binary\|hex`; omitted input reads stdin |
| Fixed fields | `--fixed-tag-size N`, `--fixed-length-size 1..8`, `--fixed-byte-order big\|little`; require Fixed |
| Resource limits | `--max-input-size N`, `--max-depth N`, `--max-elements N`; nonnegative decimal integers |
| Presentation | `--output text\|json`, `--tree`, `--pretty`, `--force-color`, `--no-color` |
| Diagnostics | `--diagnostics human\|compact\|json` |
| Semantic modules | `--module emv\|bluetooth`, `--decode`, `--describe`, `--pdol`, `--emv-check structure\|dictionary\|all` |
| EMV context | `--emv-context base\|bit\|bht\|bht-format\|bit-group\|biometric-counters\|biometric-attempts\|biometric-verification` |
| Recovery | `--recover` on dump/decode; incomplete output and status 4 when bytes were skipped |

`--count` is a flag under Query and a numeric option under Generate. `--value`
is a flag under Query and takes hex bytes under Encode. Unknown options,
duplicates, conflicts, missing values and command-specific misuse are part of
the regression contract. CER, DHCP and LLDP are Core capabilities but are not
CLI format names at this origin.

## Process and diagnostic contract

| Status | Meaning | Example baseline case |
| --- | --- | --- |
| 0 | Successful operation; scalar zero/false, unchanged diff and unknown dictionary tags can succeed | `fixed-validate`, `query-exists`, `diff-same`, `tag-unknown` |
| 1 | Invalid TLV/schema data or rejected encoded element | `ber-invalid-json`, `emv-schema-human`, `encode-invalid-element` |
| 2 | Invalid usage, hex/JSON, query syntax or unavailable format/backend | `duplicate-option`, `invalid-json`, `query-syntax-json` |
| 3 | I/O/resource/limit failure; compiled Query Reader failures also use this channel | `missing-input-file`, `element-limit`, `generate-no-overwrite` |
| 4 | Recovery skipped damaged bytes; output explicitly incomplete | `recovery-human`, `recovery-compact`, `recovery-json` |
| 5 | Node Query matched nothing | `query-missing` |

Successful validation/generation has empty stdout and stderr. Data and normal
results use stdout; diagnostics use stderr. A failing dump may have already
written valid elements; a failing JSON decode must not publish a misleading
partial document. Query explain and recovery have their own recorded stream
behavior. Human diagnostics include excerpts/paths; compact diagnostics carry
location and operation fields; JSON diagnostics retain typed locations and
expression evidence. These are compared as exact text, including JSON member
order, whitespace and final newline, subject only to the rule below.

## Comparison procedure

Copy this directory unchanged into the standalone CLI checkout (or run it from
Core while passing the standalone executable's absolute path). It needs only
Python 3.8+ and an executable with the originating full feature set:

```sh
python tools/cli/baseline/run.py compare --cli /absolute/path/to/otlv --report build/cli-baseline-report.json
```

Each invocation runs in a fresh temporary directory. Arguments use relative
fixture paths, stdin is explicit, stdout/stderr are captured separately, and
all files left behind are recorded, including unchanged inputs. Generator and
binary Encode files are compared byte-for-byte, with no JSON reserialization.
Extra/missing cases or changed case definitions fail before execution. A
mismatch names the case and changed fields, writes actual evidence when
`--report` is supplied, and exits 1. Exceptions/timeouts also fail; they cannot
be mistaken for an expected CLI exit status. Capture never overwrites evidence.

The only normalization is **CRLF to LF in textual stdout/stderr**. Raw reference
stream strings remain stored in JSON. Binary stdout and every file remain
byte-exact, including embedded CR/LF. The suite sets `LC_ALL=C`, `LANG=C`,
`TERM=dumb`, `NO_COLOR=1` and redirects streams to make the environment explicit;
the force-color case must still emit ANSI sequences. There is no trimming,
path/message replacement, JSON sorting, timestamp removal or version masking.
`--version` must still match; a later intentional release/version change needs
an explicit reviewed exception or separately named baseline, never a blind
refresh from the candidate being evaluated.

Also preserve and run the original suites. Before extraction, this runs both
original coverage and the new snapshot/infrastructure checks:

```sh
cmake -S . -B build-cli -DOPENTLV_BUILD_TESTS=OFF -DOPENTLV_BUILD_EXAMPLES=OFF -DOPENTLV_BUILD_CLI=ON -DOPENTLV_BUILD_CXX=ON -DOPENTLV_BUILD_CLI_TESTS=ON
cmake --build build-cli --config Release
ctest --test-dir build-cli -C Release -R 'Integration_cli|query-cli-conformance' --output-on-failure --no-tests=error
```

For reduced configurations, run the original capability-aware suite too. On
Linux it also exercises `/dev/full` output failure, which is deliberately not
represented as a portable file in this cross-platform snapshot. Interactive
TTY color detection and allocation exhaustion likewise remain outside this
portable subprocess capture; native/CLI-specific coverage must be retained.

## Rebuilding the reference

Create a clean detached checkout and build there, leaving this baseline suite
in the current checkout. Use the default components, static Core, C++11 and the
CLI's pinned nlohmann/json v3.11.3 dependency:

```sh
git worktree add --detach build/cli-origin e9cbb29897652fa75753ea89459e3f5e26671d3a
cmake -S build/cli-origin -B build/cli-origin-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=11 -DOPENTLV_BUILD_SHARED_LIBS=OFF -DOPENTLV_BUILD_TESTS=OFF -DOPENTLV_BUILD_EXAMPLES=OFF -DOPENTLV_BUILD_CLI=ON -DOPENTLV_BUILD_CXX=ON -DOPENTLV_BUILD_CLI_TESTS=ON
cmake --build build/cli-origin-build --config Release
ctest --test-dir build/cli-origin-build -C Release --output-on-failure --no-tests=error
python tools/cli/baseline/run.py compare --cli build/cli-origin-build/tools/cli/otlv
python tools/cli/baseline/run.py capture --cli build/cli-origin-build/tools/cli/otlv --source build/cli-origin --build-dir build/cli-origin-build --baseline build/recaptured-cli.json
```

For Visual Studio use `tools/cli/Release/otlv.exe`; Ninja on Windows uses
`tools/cli/otlv.exe`. Build in an initialized compiler environment. Compare the
recapture's observations, not its platform/compiler/binary hash metadata, when
building on another platform. Capture verifies the source SHA, clean tracked
files, tag resolution and CMake source directory; build provenance still
depends on actually completing the clean reference build shown above.

Do not regenerate `expected.json` to make a failing standalone implementation
pass. Diagnose differences, retain the report, and correct the migration or
document a separately approved behavior change. This issue establishes the
reference; standalone parity is established only when that future executable
passes the same procedure.
