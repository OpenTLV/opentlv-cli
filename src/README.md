# CLI implementation

This directory contains the `otlv` implementation migrated from
[Core `tools/cli/src`](https://github.com/OpenTLV/opentlv/tree/e9cbb29897652fa75753ea89459e3f5e26671d3a/tools/cli/src)
in [issue #3](https://github.com/OpenTLV/opentlv-cli/issues/3).
The migration preserves the C++11 sources, original license notices,
executable name, command behavior and Core version output.

Commands, argument parsing, diagnostics, JSON presentation, and shell
completion belong here. Generic TLV processing remains in Core and is consumed
through `OpenTLV::tlv` and `OpenTLV::tlv++` and their public headers.
`nlohmann_json::nlohmann_json` is a private header-only CLI dependency.

See the [command guide](../docs/README.md), [tests](../tests/README.md), and
[migration manifest](../tests/migration.json) for behavior and provenance.
Independent CLI versioning follows in issue #4.
