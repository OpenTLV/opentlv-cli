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
the validation required before creating a release tag. The complete CLI
development guide follows in [#5](https://github.com/OpenTLV/opentlv-cli/issues/5).
Removal of the original CLI from Core is tracked separately in
[Core #622](https://github.com/OpenTLV/opentlv/issues/622).

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

Core selection uses native CMake `FetchContent` in this order:

1. An explicit `FETCHCONTENT_SOURCE_DIR_OPENTLV_CORE` uses that checkout and
   skips package discovery and Git downloads/updates.
2. Otherwise, `FIND_PACKAGE_ARGS CONFIG NAMES OpenTLV` searches installed
   `OpenTLVConfig.cmake` packages.
3. If none is found, Core is fetched at the full commit SHA in
   [cmake/Core.cmake](cmake/Core.cmake):
   `edebe957ee2a1e0bf5685c3bd55a33788446e80d`.

Both `OpenTLV::tlv` and `OpenTLV::tlv++` must exist. An installed package or
local checkout missing either target is rejected with a diagnostic. Older
packages exporting `OpenTLV::tlvpp` are not compatible. The numeric Core
version alone cannot distinguish the public target change made after 0.7.1.

Source builds use Core's embedded defaults: libraries and the C++ facade,
with its CLI, examples, and native tests disabled. Core implementation code
is not copied here and no sibling directory is detected automatically.

The CLI also consumes header-only [nlohmann/json](https://github.com/nlohmann/json)
3.11.3 for JSON presentation and input. An explicit
`FETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON` selects a local source tree;
otherwise CMake searches for an installed 3.11.3 package before fetching the
pinned commit `9cca280a4d0ccf0c08f47a99aa71d1b0e52f8d03`.
This dependency belongs to the CLI; Core's C/C++ libraries remain independent
of JSON.

## Local workspace and offline use

Recommended layout:

```text
OpenTLV/
  opentlv/
  opentlv-cli/
  opentlv-docs/
  opentlv-workspace/
```

From `opentlv-cli`:

```sh
cmake --preset workspace
cmake --build --preset workspace
ctest --preset workspace
```

The workspace preset explicitly sets
`FETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=${sourceDir}/../opentlv`.
This checkout must exist. To use a different path:

```sh
cmake --preset workspace -DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=/absolute/path/to/opentlv
```

For a fully offline source build, also supply nlohmann/json 3.11.3 locally:

```sh
cmake --preset workspace -DFETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON=/absolute/path/to/json
cmake --build --preset workspace
ctest --preset workspace
```

Alternatively, make its installed CMake package available through
`CMAKE_PREFIX_PATH`. A local Core checkout alone does not prevent a JSON
download. Source overrides take precedence over installed packages, and CMake
does not update or switch these checkouts. Compilers, build tools and Python
must already be installed. The
[VS Code workspace](https://github.com/OpenTLV/opentlv-workspace) is optional.

## Installed Core

Build and install a Core revision containing the public integration from
[Core #620](https://github.com/OpenTLV/opentlv/issues/620), with its C++ facade
enabled. Select its installation prefix in a fresh CLI build directory:

```sh
cmake -S . -B build/package -DCMAKE_PREFIX_PATH=/absolute/path/to/core-install
cmake --build build/package --config Release
ctest --test-dir build/package -C Release --output-on-failure --no-tests=error
```

A compatible installed package needs no Core download. If discovery fails,
CMake proceeds to Git fallback. An incompatible package that was found fails
explicitly; use a compatible prefix or the explicit local source override.
JSON is selected separately as described above.

Use a fresh build directory when switching between package and source modes
to avoid stale discovery cache entries. The integration tests cover both
static and shared Core, including Windows DLL placement beside the executable
and dependency consumers.

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

- `OPENTLV_CLI_BUILD_TESTS=OFF` disables dependency and CLI regression tests.
- `OPENTLV_BUILD_SHARED_LIBS=ON/OFF` selects shared/static Core for source
  builds. Installed packages retain their own build configuration.
- Keep `OPENTLV_BUILD_CXX=ON` for source builds; CLI requires the C++ facade.
  Reader, Writer, Query with its text frontend, Schema and Codec must be enabled.
  Document and individual protocol formats may be disabled.
- Core component options control available formats and features. Tests inspect
  the public Core configuration, including when consuming an installed package.
- To exercise Git fallback explicitly, configure a fresh directory with
  `FETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER` and no source overrides.

To update a pinned dependency revision, change its full `GIT_TAG` SHA and
matching documentation, then run the dependency matrix and command suites
in [tests/README.md](tests/README.md). Preserve the frozen migration baseline;
never regenerate its expected observations from the candidate executable.
Record meaningful changes in the changelog. Local and installed modes
intentionally allow a separately selected Core revision.

## Repository layout

| Path | Purpose |
| --- | --- |
| `CMakeLists.txt`, `cmake/` | Standalone project and public dependency resolution |
| `CMakePresets.json` | Standalone and explicit workspace configure/build/test presets |
| `src/` | CLI commands, argument parsing, diagnostics, output and shell completions |
| `tests/` | Dependency consumers, CLI regression suites and migration provenance |
| `docs/` | CLI command guide and versioned JSON document schema |
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
