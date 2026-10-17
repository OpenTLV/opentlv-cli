# OpenTLV CLI

Official command-line interface for [OpenTLV Core](https://github.com/OpenTLV/opentlv).
The executable is **`otlv`** (`otlv.exe` on Windows). It inspects and validates
TLV data, encodes and decodes JSON documents, runs queries and semantic diffs,
and generates reproducible wire corpora through Core's public APIs.

## Current status

The standalone project builds the existing CLI implementation and its command
regression suites. Commands, arguments, diagnostics, exit codes and output
remain covered by the frozen migration baseline. See the
[command guide](docs/README.md) and [JSON document schema](docs/json-schema.md).

`otlv --version` reports `OpenTLV CLI <version>`, derived from this repository's
`vMAJOR.MINOR.PATCH` Git tags independently of Core. See the
[version and release guide](docs/releases.md) for development versions and
the validation required before creating a release tag. The
[development guide](docs/development.md) covers build configurations, dependency
selection, offline use and Core updates.

## Requirements

- CMake 3.24 or newer.
- A C compiler and a C++11-capable compiler, plus the generator's build tool.
  Core requires Clang 18 or newer when using Clang.
- Git and network access for dependencies not supplied locally or installed.
- Python 3.10+ for the command regression suites, dependency matrix runner,
  and contributor tools.

Windows can use the installed Visual Studio generator. For Ninja, initialize
the compiler environment and add `-G Ninja` when configuring. The presets
leave generator selection to CMake and use separate build directories.

## Standalone build

```sh
git clone https://github.com/OpenTLV/opentlv-cli.git
cd opentlv-cli
cmake --preset default
cmake --build --preset default
ctest --preset default
```

The executable is `build/default/src/otlv` for single-configuration generators,
or `build/default/src/Release/otlv.exe` for Visual Studio Release builds. Try:

```sh
build/default/src/otlv dump --format fixed --hex "01 02 48 69"
```

Core selection prefers an explicit local source override, then an installed
package, then the immutable Git pin in [cmake/Core.cmake](cmake/Core.cmake).
Both public targets `OpenTLV::tlv` and `OpenTLV::tlv++` are required.
The private header-only nlohmann/json 3.11.3 dependency is resolved separately.
See [dependency resolution](docs/development.md#dependency-resolution) for
selection rules, compatibility requirements and a forced pinned build.

## Local workspace and offline use

Place `opentlv` and `opentlv-cli` side by side, then run from `opentlv-cli`:

```sh
cmake --preset workspace
cmake --build --preset workspace
ctest --preset workspace
```

The workspace preset explicitly selects `../opentlv`; CMake does not detect
siblings automatically. For a fully offline build, also supply nlohmann/json
3.11.3 through `FETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON` or an installed package.
See the [workspace layout and setup](docs/development.md#local-workspace),
[preset reference](docs/development.md#presets-and-build-configurations) and
[offline requirements](docs/development.md#offline-builds).

## Installed Core

A compatible installed Core package can be selected with `CMAKE_PREFIX_PATH`
or `opentlv_core_DIR`. It must provide both public targets and the required
capabilities. Use a fresh build directory when changing dependency modes;
see the [installed-package procedure](docs/development.md#installed-core-package).
JSON is selected separately.

## Install

```sh
cmake --install build/default --config Release --prefix install-cli
```

`otlv` is installed in the standard runtime directory, normally `bin`.
When Core is built from source in the same build, its install rules also
install the library runtime. Retain that installation layout. When consuming
an installed shared Core package, make its runtime libraries available on the
platform's library search path when deploying `otlv`.

## Options and dependency updates

The [development guide](docs/development.md#supported-core-configurations)
describes supported shared/static and component configurations, test options,
and Debug/Release builds. Follow its
[Core update procedure](docs/development.md#updating-the-pinned-core-revision)
when changing the immutable dependency pin. Preserve historical migration
provenance and the frozen regression baseline.

## Repository layout

| Path | Purpose |
| --- | --- |
| `CMakeLists.txt`, `cmake/` | Standalone project and public dependency resolution |
| `CMakePresets.json` | Standalone and explicit workspace configure/build/test presets |
| `src/` | CLI commands, argument parsing, diagnostics, output and shell completions |
| `tests/` | Dependency consumers, CLI regression suites and migration provenance |
| `docs/` | Command, development and release guides, and versioned JSON document schema |
| `.github/` | Windows/Linux CI, issue forms, and pull request template |
| `CONTRIBUTING.md` | Development and contributor checks |
| `CHANGELOG.md` | Independent CLI change history and migration provenance |

## Ownership

Core owns public C/C++ APIs, execution semantics, canonical semantic fixtures,
and shared native tests. This repository owns CLI behavior, process tests,
command documentation and independent releases. Immutable fixture snapshots retain
Core provenance. [OpenTLV Docs](https://github.com/OpenTLV/opentlv-docs)
assembles and publishes documentation.

## License

MIT; see [LICENSE](LICENSE). The original Core CLI carries
`Copyright (c) 2026 Marek Cingel`. Preserve that notice in migrated sources
and retain third-party notices. This repository also retains its existing
OpenTLV copyright attribution.
