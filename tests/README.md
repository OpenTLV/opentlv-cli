# CLI tests

## Core dependency integration

Normal CLI configuration builds two small executables. They consume only
`OpenTLV::tlv` and `OpenTLV::tlv++`, exercising public headers, transitive
linkage, and runtime version metadata. The C check also compares header and
runtime Git revision metadata. Windows shared builds copy the Core DLL beside
each executable using the public target's location.

```sh
cmake --preset workspace
cmake --build --preset workspace
ctest --preset workspace
```

These are dependency smoke tests, not command regression tests.

Run the full integration matrix from the CLI root:

```sh
python tests/check_core_dependency.py --shared ON
python tests/check_core_dependency.py --shared OFF
```

The runner requires Python 3.10+, CMake, Git, and the compiler/build tools.
It uses a new directory under `build/dependency-check/` for every run.
Select a generator with `--generator Ninja` if needed.

Each run checks:

- Real Git fallback with the configured full SHA and package lookup disabled.
- Explicit local Core selection with a discoverable package trap.
- Discovery and use of a relocated real Core installation.
- Local override precedence with a valid installed package present.
- Rejection of missing C/C++ public targets and the legacy `tlvpp` target.
- Rejection of a C++-disabled Core checkout.
- Failure for a missing explicit checkout without silently selecting a package.
- The workspace preset from a separate checkout layout.

Successful modes compile and run both consumers. Local/package/preset cases
forbid Git network transports, including on the first configure. The relocated
installation is a separate copy whose CMake exports are checked for original
source, build, and install paths. Temporary files stay inside the test run.
No developer checkout is modified.

For offline checks against an existing checkout:

```sh
python tests/check_core_dependency.py --core-source ../opentlv --skip-git --shared ON
```

This explicitly skips remote fallback validation. The full runner downloads
Core and requires network access. Per-command logs and `summary.json` retain
the selected revisions, dirty-state markers, linkage mode, and outcomes.
CI runs the full matrix on Windows and Linux for both shared and static Core.
A local run does not establish hosted CI success.

## Command regression migration

CLI-owned integration tests, process/file fixtures, and the frozen migration
baseline move here in [issue #3](https://github.com/OpenTLV/opentlv-cli/issues/3).

Preserve exit codes, stdout, stderr, diagnostics, and output files against the
Core baseline recorded in [CHANGELOG.md](../CHANGELOG.md). Existing command
tests remain required alongside the frozen baseline.

Shared native Core tests, the canonical Query corpus, and protocol fixtures
remain owned by Core. Migration may retain versioned fixture snapshots with
their source revision and attribution.
