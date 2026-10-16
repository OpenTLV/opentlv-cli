# OpenTLV CLI

Official command-line interface for OpenTLV, being extracted into an independent
repository from [OpenTLV Core](https://github.com/OpenTLV/opentlv).
The executable name remains **`otlv`** (`otlv.exe` on Windows).

## Current status

The standalone project resolves Core and builds C/C++ dependency smoke tests.
The CLI executable and command regression suite are migrated in
[#3](https://github.com/OpenTLV/opentlv-cli/issues/3). The existing CLI remains
in Core until that migration passes validation.

Independent versioning and release gates follow in
[#4](https://github.com/OpenTLV/opentlv-cli/issues/4); the complete CLI development
guide follows in [#5](https://github.com/OpenTLV/opentlv-cli/issues/5).
[Core #619](https://github.com/OpenTLV/opentlv/issues/619) coordinates extraction.

## Requirements

- CMake 3.24 or newer.
- A C compiler and a C++11-capable compiler, plus the generator's build tool.
  Core requires Clang 18 or newer when using Clang.
- Git and network access for the initial Git fallback.
- Python 3.10+ for the optional dependency matrix runner and contributor tools.

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

Dependency selection uses native CMake `FetchContent` in this order:

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
with its CLI, examples, and native tests disabled. No Core source is vendored
into this repository and no sibling directory is detected automatically.

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

The source override takes precedence even when an installed package is
available. With the compiler and build tools installed, this mode needs no
network access for dependencies. CMake does not update or switch the checkout.
The [VS Code workspace](https://github.com/OpenTLV/opentlv-workspace) is optional.

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

Use a fresh build directory when switching between package and source modes
to avoid stale discovery cache entries. The integration tests cover both
static and shared Core, including Windows DLL placement beside the test
executables.

## Options and dependency updates

- `OPENTLV_CLI_BUILD_TESTS=OFF` disables the two dependency smoke tests.
- `OPENTLV_BUILD_SHARED_LIBS=ON/OFF` selects shared/static Core for source
  builds. Installed packages retain their own build configuration.
- Keep `OPENTLV_BUILD_CXX=ON` for source builds; CLI requires the C++ facade.
- To exercise Git fallback explicitly, configure a fresh directory with
  `FETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER` and no source override.

To update the pinned revision, change the full `GIT_TAG` SHA in
`cmake/Core.cmake`, update this README, and run the dependency matrix described
in [tests/README.md](tests/README.md). Record the meaningful change in the
changelog. The local and installed modes intentionally allow a separately
selected Core revision.

## Repository layout

| Path | Purpose |
| --- | --- |
| `CMakeLists.txt`, `cmake/Core.cmake` | Standalone project and public Core resolution |
| `CMakePresets.json` | Standalone and explicit workspace configure/build/test presets |
| `src/` | Destination for the CLI implementation |
| `tests/` | Dependency consumers, matrix runner, and future CLI regression tests |
| `.github/` | Dependency CI, issue forms, and pull request template |
| `CONTRIBUTING.md` | Development and contributor checks |
| `CHANGELOG.md` | Independent CLI change history and migration provenance |

## Ownership

Core owns public C/C++ APIs, execution semantics, and shared native tests.
This repository owns CLI behavior, tests, and future releases.
[OpenTLV Docs](https://github.com/OpenTLV/opentlv-docs) assembles and publishes
documentation; CLI documentation belongs here as it is migrated.
CLI and Core versions are independent.

## License

MIT; see [LICENSE](LICENSE). The original Core CLI carries
`Copyright (c) 2026 Marek Cingel`. Preserve that notice in migrated sources
and retain third-party notices. This repository also retains its existing
OpenTLV copyright attribution.
