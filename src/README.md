# CLI implementation

The existing `otlv` implementation will be migrated here in
[issue #3](https://github.com/OpenTLV/opentlv-cli/issues/3), after public Core
dependency integration in [#2](https://github.com/OpenTLV/opentlv-cli/issues/2).

Keep the executable name `otlv`, C++11 compatibility, and existing behavior.
Consume Core through its public targets and APIs; preserve original license
notices. No placeholder application is provided by the bootstrap.
