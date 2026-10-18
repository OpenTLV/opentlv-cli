# CLI tests

## Documentation notification checks

The quality workflow also exercises the documentation notifier with Node.js 24:

```sh
node --test tests/test_docs_notification.cjs
```

These tests execute the actual workflow's API script with mocked artifact reads
and dispatch calls. They cover candidate versus workflow SHA, prerelease
notifications, safe resend, stale attempts and rejected evidence. They do not
send real notifications or replace hosted end-to-end publication validation.
Node.js is needed for these tooling checks, not to build or run `otlv`.

## Run the regression suites

With Core and nlohmann/json available as described in the
[development guide](../docs/development.md), run:

```sh
cmake --preset workspace
cmake --build --preset workspace
ctest --preset workspace
```

CTest includes both dependency smoke tests and the migrated command suites:

| Test | Coverage |
| --- | --- |
| `Integration_cli` | Original capability-aware command, argument, input/output, diagnostic, semantic-module and generation assertions |
| `Integration_cli_cpp_examples` | CLI equivalents of Core C++ parsing, writing, Query and JSON examples |
| `query-cli-conformance` | Pinned Query corpus through the auto and Document backends |
| `Integration_cli_baseline` | 153 frozen observations plus the issue #4 CLI version contract |
| `Integration_cli_baseline_runner` | 7 comparator unit tests guarding evidence comparison |
| `Integration_cli_migration` | Frozen fixture integrity against the migration manifest |
| `cli_version` | Exact stdout, empty stderr and successful exit for the built CLI version |
| `cli_version_contract` | Git tags, prereleases, development/dirty/source-export versions and candidate restrictions |
| `cli_release_gate` | Rejection of invalid inputs, incomplete or stale evidence, failures and skips |

Run all tests when checking the migration. The historical Query test has the
`query;conformance;memcheck-full` labels, so selecting only `integration` does
not include it. Python 3.10+ is required when CLI tests are enabled.

The suites obtain capabilities from a small executable compiled against the
public Core configuration header. This also works with installed packages,
where Core's source-build CMake options are unavailable. The original command
suite always exercises the selected build. Examples require BER, and Query
conformance requires BER, Query frontend and Document. The complete frozen
baseline additionally requires DER, EMV, Bluetooth and NFC. Reduced builds
explicitly skip suites whose capabilities are unavailable; they never compare
a silently reduced baseline.

## Frozen behavior comparison

The unchanged [baseline](baseline/README.md) records Core origin
`e9cbb29897652fa75753ea89459e3f5e26671d3a`, the preceding release tag and capture
provenance. Its Core-relative paths are historical references. In this
repository the comparator can also be run directly:

```sh
python -B tests/check_cli_baseline.py --cli build/default/src/otlv --version <cli-version> --report build/baseline-report.json
```

For Visual Studio, use `build/default/src/Release/otlv.exe`. The comparator
checks exit status, separate stdout/stderr, and resulting file contents.
Only textual stdout/stderr CRLF-to-LF normalization is permitted; binary
streams and files remain exact. Read `<cli-version>` from the build's
`cli-version.txt`. The issue #4 comparator changes only the expected `version`
observation to `OpenTLV CLI <cli-version>`, retaining exact exit/stderr/file
checks. Its report records this intentional change. The original comparator,
case inventory and captured evidence in `baseline/` remain byte-for-byte intact
and can still verify the historical Core CLI.

Never recapture `expected.json` from the candidate to make a mismatch pass.
The baseline supplements the original suites; it does not replace their edge
coverage or the native Core contracts.

## Core dependency integration

Two small consumers link only `OpenTLV::tlv` and `OpenTLV::tlv++`, exercising
public headers, transitive linkage, and runtime version metadata. The C check
also compares header and runtime Git revision metadata. Windows shared builds
copy the Core DLL beside the executable and consumers using the public target's
location.

Run the full integration matrix from the CLI root:

```sh
python -B tests/check_core_dependency.py --shared ON
python -B tests/check_core_dependency.py --shared OFF
```

The runner requires Python 3.10+, CMake, Git, and the compiler/build tools.
It uses a new directory under `build/dependency-check/` for every run.
Select a generator with `--generator Ninja` if needed.

Each run checks:

- Real Git fallback with package lookup explicitly disabled and a discoverable
  package trap. The fetched SHA must equal the pin, and both public targets
  must be non-imported targets originating inside that checkout.
- Explicit local Core selection with a discoverable package trap.
- Discovery and use of a relocated real Core installation.
- Local override precedence with a valid installed package present.
- Rejection of missing C/C++ public targets and the legacy `tlvpp` target.
- Rejection of a C++-disabled Core checkout.
- Failure for a missing explicit checkout without silently selecting a package.
- The workspace preset from a separate checkout layout.

Successful modes build `otlv` and both consumers, then run CTest including the
command suites. Local/package/preset cases forbid Git network transports,
including on the first configure, and receive a local JSON source tree.
The relocated installation is a separate copy whose CMake exports are checked
for original source, build, and install paths. Temporary files stay inside the
test run. No developer checkout is modified.

For offline checks against existing checkouts:

```sh
python -B tests/check_core_dependency.py --core-source ../opentlv --json-source /absolute/path/to/json --skip-git --shared ON
```

This explicitly skips remote fallback validation. The JSON checkout must
supply nlohmann/json 3.11.3. The full runner downloads dependencies when local
sources are not supplied and requires network access. Per-command logs and
`summary.json` retain selected revisions, dirty-state markers, linkage mode,
and outcomes, compiler identity, CLI version, and all CTest results. Release CI
runs the full matrix on Windows and Linux for shared and static Core. PR CI
runs one pinned build per platform, all its applicable suites, formatting and
static checks. A local run does not establish hosted CI success.

`--release-request <request.json>` is reserved for the release workflow. It
requires the exact clean CLI commit and pinned Core/JSON revisions, forbids
overrides and skipped Git fallback, and checks all 11 CTest entries in each
of five successful dependency scenarios. It rejects unexpected suite skips;
the two named Query fixture-provider exclusions remain explicit. See the
[release guide](../docs/releases.md) for evidence and tag creation.

## Fixture ownership and provenance

The [migration manifest](migration.json) records source paths, revisions and
hashes. `python tests/check_migration.py --all-imports` also audits the initial
source import; the normal test checks immutable fixtures so CLI code can evolve.
CLI-owned files include `test.cmake`, `examples.cmake`, `input.bin`,
the Query process runner and the unchanged `baseline/` directory.

`query/corpus.json` is an immutable snapshot of Core's canonical Query corpus:
171 cases, with two explicit exclusions for external fixture/provider name
resolution. The remaining 169 cases run through both backends for 338
executions. `fixtures/nfc/type2/` retains the valid and malformed protocol
examples needed by the original CLI suite. Preserve their source provenance
when updating snapshots.

Shared Query semantics, canonical protocol fixtures, native C/C++ tests,
generator properties and other language runners remain owned by Core. CLI
process assertions cover command parsing, presentation, diagnostics and files.
