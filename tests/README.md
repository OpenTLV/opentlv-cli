# CLI tests

CLI-owned integration tests, process/file fixtures, and the frozen migration
baseline will move here in
[issue #3](https://github.com/OpenTLV/opentlv-cli/issues/3).

Preserve exit codes, stdout, stderr, diagnostics, and output files against the
Core baseline recorded in [CHANGELOG.md](../CHANGELOG.md). Existing command
tests remain required alongside the frozen baseline.

Shared native Core tests, the canonical Query corpus, and protocol fixtures
remain owned by Core. Migration may retain versioned fixture snapshots with
their source revision and attribution.

There are no executable tests at the bootstrap stage. Configuring CMake is not
evidence of runtime or regression compatibility.
