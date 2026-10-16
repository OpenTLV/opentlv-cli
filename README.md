# OpenTLV CLI

Official command-line interface for OpenTLV, being extracted into an independent
repository from [OpenTLV Core](https://github.com/OpenTLV/opentlv).
The executable name remains **`otlv`** (`otlv.exe` on Windows).

## Current status

This repository currently provides the project foundation only. CMake can
configure and generate the standalone build, but there is no executable or
runtime test suite yet. The existing CLI remains available in Core until the
standalone migration passes regression validation.

- [#2](https://github.com/OpenTLV/opentlv-cli/issues/2): public Core dependency integration.
- [#3](https://github.com/OpenTLV/opentlv-cli/issues/3): implementation and regression-test migration.
- [#4](https://github.com/OpenTLV/opentlv-cli/issues/4): independent CI, versioning, and release gates.
- [#5](https://github.com/OpenTLV/opentlv-cli/issues/5): complete standalone and workspace development guide.

The extraction is coordinated by [Core #619](https://github.com/OpenTLV/opentlv/issues/619).
No Core source or Git history is copied by this bootstrap.

## Configure

Requirements: Git, CMake 3.24 or newer, a C++11-capable compiler, and a build tool
supported by the selected CMake generator.

```sh
git clone https://github.com/OpenTLV/opentlv-cli.git
cd opentlv-cli
cmake -S . -B build
cmake --build build --config Release
```

On Windows, CMake can select an installed Visual Studio generator. For Ninja,
run from a shell with the compiler environment initialized and add `-G Ninja`
to the configure command.

The build currently has no application targets. A successful configure/build
checks the foundation only; it is not CLI regression validation. This step
neither discovers nor downloads Core or JSON dependencies.

## Repository layout

| Path | Purpose |
| --- | --- |
| `CMakeLists.txt` | Independent CMake project |
| `src/` | Destination for the existing CLI implementation |
| `tests/` | Destination for CLI-owned tests and migration fixtures |
| `.github/` | Issue forms and pull request template |
| `CONTRIBUTING.md` | Development and contributor checks |
| `CHANGELOG.md` | Independent CLI change history and migration provenance |

For local development, the repositories can be siblings:

```text
OpenTLV/
  opentlv/
  opentlv-cli/
  opentlv-docs/
  opentlv-workspace/
```

The [VS Code workspace](https://github.com/OpenTLV/opentlv-workspace) is optional.
This layout does not automatically discover or configure Core. Local source
overrides, installed packages, and pinned Git fallback are implemented in #2.

## Ownership

Core owns public C/C++ APIs, execution semantics, and shared native tests.
This repository owns the CLI application, its process-level behavior, tests,
and future releases. [OpenTLV Docs](https://github.com/OpenTLV/opentlv-docs)
owns documentation assembly and publishing; CLI documentation belongs here
as it is migrated. CLI and Core versions are independent.

See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and review conventions,
and [CHANGELOG.md](CHANGELOG.md) for the recorded Core origin.

## License

MIT; see [LICENSE](LICENSE). The original Core CLI carries
`Copyright (c) 2026 Marek Cingel`. Preserve that notice in migrated sources
and retain any third-party notices. This repository also retains its existing
OpenTLV copyright attribution.
