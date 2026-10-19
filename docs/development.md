# CLI development

This guide covers building and testing `otlv` from the standalone CLI
repository or alongside a Core checkout. Run commands from `opentlv-cli`
unless a step says otherwise. See the [command guide](README.md) for CLI use,
[contributor guide](../CONTRIBUTING.md) for formatting and license checks, and
[release guide](releases.md) for independent versioning and release validation.

## Requirements

- CMake 3.24 or newer.
- A C compiler and a C++11-capable compiler, plus the generator's build tool.
  Core requires Clang 18 or newer when using Clang.
- Python 3.10+ when tests are enabled (the default), and for contributor tools.
- Git and network access to clone the CLI and fetch dependencies that are not
  supplied locally. Use a full CLI clone with history and tags; shallow clones
  are rejected by version generation.

The presets leave the generator to CMake. Windows can use Visual Studio 2022;
for Ninja with MSVC, open a developer shell with the compiler environment
initialized. Add `-G Ninja` at the first configure if desired. Use a separate
build directory for each generator or compiler.

## Standalone build

```sh
git clone https://github.com/OpenTLV/opentlv-cli.git
cd opentlv-cli
cmake --preset default
cmake --build --preset default
ctest --preset default
```

No separate Core checkout is required. CMake looks for an installed Core
package and otherwise downloads the pinned source revision. JSON is resolved
separately. To require the pinned sources even when packages are installed,
use the [Git fallback procedure](#pinned-git-fallback).

For a single-configuration generator, the executable is
`build/default/src/otlv` (`otlv.exe` on Windows). Visual Studio puts it in
`build/default/src/Release/otlv.exe`. For example, on PowerShell with Visual
Studio:

```powershell
./build/default/src/Release/otlv.exe dump --format fixed --hex "01 02 48 69"
```

Expected output:

```text
offset=0 tag=01 length=2 value=4869
```

## Local workspace

Recommended sibling layout:

```text
workspace/
  opentlv/
  opentlv-cli/
  opentlv-docs/
  opentlv-workspace/
```

Only `opentlv` and `opentlv-cli` are needed for this build. The documentation
portal and [VS Code workspace](https://github.com/OpenTLV/opentlv-workspace)
are optional. Starting in an empty workspace directory:

```sh
git clone https://github.com/OpenTLV/opentlv.git
git clone https://github.com/OpenTLV/opentlv-cli.git
cd opentlv-cli
cmake --preset workspace
cmake --build --preset workspace
ctest --preset workspace
```

The workspace preset explicitly selects
`FETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=${sourceDir}/../opentlv`. CMake does not
search for siblings automatically. A missing checkout is an error, with no
package or Git fallback. CMake builds that checkout as a dependency without
checking out a different revision or updating it. Rebuild the CLI after Core
changes; rerun configuration when changing build options.

To select a different checkout, replace the example path:

```sh
cmake --preset workspace -DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=/absolute/path/to/opentlv
```

A path containing spaces must be quoted as a single argument, for example
`"-DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=D:/My Projects/opentlv"`.
The JSON dependency may still need a download; see [offline builds](#offline-builds).

## Presets and build configurations

[CMakePresets.json](../CMakePresets.json) defines these configure, build and
test presets:

| Preset | Build directory | Core selection | Configuration |
| --- | --- | --- | --- |
| `default` | `build/default` | Installed package, then pinned Git fallback | Release |
| `workspace` | `build/workspace` | Explicit sibling `../opentlv` | Release |

List them with `cmake --list-presets=all`. Both test presets show failures and
fail if no tests are found. Neither preset disables tests. Both build and test
presets select `Release` for multi-configuration generators; the configure
presets set `CMAKE_BUILD_TYPE=Release` for single-configuration generators.

For debugging with Ninja or Makefiles, use a separate directory and matching
configuration throughout. Replace `/absolute/path/to/opentlv` with your Core
checkout's absolute path:

```sh
cmake -S . -B build/debug -G Ninja -DCMAKE_BUILD_TYPE=Debug -DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=/absolute/path/to/opentlv
cmake --build build/debug
ctest --test-dir build/debug --output-on-failure --no-tests=error
```

For Visual Studio, select the configuration at build and test time:

```sh
cmake -S . -B build/debug-vs -G "Visual Studio 17 2022" -DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE=/absolute/path/to/opentlv
cmake --build build/debug-vs --config Debug
ctest --test-dir build/debug-vs -C Debug --output-on-failure --no-tests=error
```

The same pattern supports `RelWithDebInfo` with generators that provide it.
Do not build Debug and then use a test preset that still selects Release.
An installed Core package must provide a compatible configuration and runtime;
source mode is convenient when developing Core and CLI together.

For persistent personal settings, use the Git-ignored `CMakeUserPresets.json`.
This example adds a local static build and keeps its directory separate:

```json
{
  "version": 5,
  "configurePresets": [
    {
      "name": "local-static",
      "inherits": "workspace",
      "binaryDir": "${sourceDir}/build/local-static",
      "cacheVariables": {
        "OPENTLV_BUILD_SHARED_LIBS": "OFF"
      }
    }
  ],
  "buildPresets": [
    { "name": "local-static", "inherits": "workspace", "configurePreset": "local-static" }
  ],
  "testPresets": [
    { "name": "local-static", "inherits": "workspace", "configurePreset": "local-static" }
  ]
}
```

Configure, build and test with `--preset local-static` using the corresponding
tools. Do not overwrite an existing user presets file; merge the entries.

## Dependency resolution

Core selection in [cmake/Core.cmake](../cmake/Core.cmake) follows this order:

1. `FETCHCONTENT_SOURCE_DIR_OPENTLV_CORE` selects explicit source and bypasses
   package lookup and Git downloads/updates for Core.
2. Without that override, `FIND_PACKAGE_ARGS CONFIG NAMES OpenTLV` enables
   CMake package discovery for `OpenTLVConfig.cmake`.
3. If no package is found, FetchContent downloads the full commit SHA in
   `GIT_TAG` and builds it as a dependency.

The selected Core must export `OpenTLV::tlv` and `OpenTLV::tlv++`. Packages
exporting the old `OpenTLV::tlvpp` target are incompatible. The numeric Core
version alone does not prove compatibility with the public integration from
[Core #620](https://github.com/OpenTLV/opentlv/issues/620).

Core source builds use its embedded library defaults. The CLI consumes public
targets, headers and APIs; Core implementation code is not copied into CLI.

JSON selection in [cmake/Json.cmake](../cmake/Json.cmake) is independent:
`FETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON`, then an installed **3.11.3 exact**
`nlohmann_json` package, then the pinned Git commit. Supply version 3.11.3
when providing a local JSON source tree. This header-only dependency belongs
to CLI and does not add a JSON dependency to Core libraries.

### Installed Core package

Build and install a compatible Core with its C++ facade enabled using Core's
public build instructions. Select the installation prefix in a fresh CLI
directory:

```sh
cmake -S . -B build/package -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/absolute/path/to/core-install
cmake --build build/package --config Release
ctest --test-dir build/package -C Release --output-on-failure --no-tests=error
```

Alternatively, `opentlv_core_DIR` can point directly to the directory containing
`OpenTLVConfig.cmake`. FetchContent calls
`find_package(opentlv_core CONFIG NAMES OpenTLV)`, so the cache variable uses
the dependency name `opentlv_core`, even though the config file is named
`OpenTLVConfig.cmake`. Multiple installation prefixes can be supplied as one
quoted semicolon-separated `CMAKE_PREFIX_PATH` value, including a JSON prefix.
Keep Core and JSON source overrides unset when testing package discovery.

If no package is found, Git fallback is allowed. If a package is found but
its required targets or capabilities are missing, configuration or compilation
fails; CLI does not silently replace that incompatible package with a Git copy.
Installed libraries retain their own configuration: changing Core source-build
options in CLI does not rebuild an installed Core.

### Pinned Git fallback

Use a fresh directory with package lookup disabled and no source overrides:

```sh
cmake -S . -B build/pinned -DCMAKE_BUILD_TYPE=Release -DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER
cmake --build build/pinned --config Release
ctest --test-dir build/pinned -C Release --output-on-failure --no-tests=error
```

This selects the pins from `cmake/Core.cmake` and `cmake/Json.cmake`; it needs
Git and network access on the first configure. `NEVER` affects both dependencies.
An explicit source override still wins over this setting. The dependency
matrix verifies the fetched SHA and target provenance as described in the
[test guide](../tests/README.md#core-dependency-integration).

### Switching modes

Keep separate directories for workspace, package and pinned builds. Switch
from local Core to pinned Core by running the pinned procedure above, and
back by using the workspace preset. `default` permits installed packages,
so it is not an assertion that the pin was used.

CMake caches source overrides and package locations. Reusing a directory
without clearing that configuration can retain the previous dependency mode.
Changing a preset name or setting package lookup to `NEVER` does not remove a
cached source override. A fresh directory also avoids generator, compiler and
installed-package cache conflicts. Do not edit the fetched `_deps` checkout
to maintain local Core changes; select your own checkout explicitly.

### Offline builds

Prepare the compiler, build tool, CMake, Python and dependency sources or
installed packages before disconnecting. For a source build, supply both
Core and nlohmann/json 3.11.3:

```sh
cmake --preset workspace -DFETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON=/absolute/path/to/json
cmake --build --preset workspace
ctest --preset workspace
```

These explicit source overrides work on the first configure without fetching
either dependency. CMake does not update their checkouts. Installed packages
for both dependencies are another option, provided discovery succeeds. A local
Core checkout alone does not prevent a JSON download. Merely setting
`FETCHCONTENT_FULLY_DISCONNECTED=ON` does not provision missing dependencies
and is not a replacement for supplying them.

Contributor tooling has separate offline requirements: install its dedicated
Python environment and populate pre-commit hook environments while online.
See [contributor tools](../CONTRIBUTING.md#contributor-tools). The full dependency
matrix intentionally checks real Git fallback and needs network access; its
documented `--skip-git` mode provides partial offline validation only.

## Supported Core configurations

| Setting | Effect |
| --- | --- |
| `OPENTLV_CLI_BUILD_TESTS=ON/OFF` | Enable/disable CLI tests and dependency smoke tests; defaults to ON for standalone builds |
| `OPENTLV_BUILD_SHARED_LIBS=ON/OFF` | Select shared/static Core when building from source |
| `OPENTLV_BUILD_CXX=ON` | Required C++ facade for source builds |
| Core component options | Control available formats and optional features in source builds |

Reader, Writer, Query with its text frontend, Schema and Codec are required.
Document and individual protocol formats may be disabled. The compiler checks
the selected Core's public configuration, including installed packages.
For example, select static Core with
`cmake --preset workspace -DOPENTLV_BUILD_SHARED_LIBS=OFF` and then build/test
that preset. Retain full capabilities for the complete regression and release
checks. Reduced builds explicitly skip suites that need unavailable features;
those skips do not constitute full release validation.

## Tests and contributor checks

After building, run `ctest --preset default` or `ctest --preset workspace`.
CTest includes dependency consumers, command regressions, the frozen baseline,
Query conformance, version contracts and release-gate tests. Run all entries
for complete coverage; filtering only the `integration` label omits Query and
some tooling tests. See the [test guide](../tests/README.md) for detailed
coverage, capability skips, direct runners and the shared/static dependency matrix.

For formatting, license metadata and static analysis, follow
[CONTRIBUTING.md](../CONTRIBUTING.md#validation). Keep local results separate
from hosted CI evidence. A development build or a local passing test suite
does not establish hosted release readiness.

## Updating the pinned Core revision

1. Select a full, immutable Core commit SHA that supplies the required public
   targets and capabilities. First develop against an explicit local checkout
   if changes to Core and CLI must be tested together.
2. Update `GIT_TAG` in `cmake/Core.cmake`. Keep a full SHA, not a moving branch.
   Update the matching commit in `cmake/core-artifact.json`; select a published
   schema-2 Core release there to enable authenticated release consumption.
   Update documentation that describes the current dependency and record the
   change under `Unreleased`. Historical migration/provenance references must
   continue to identify their original source revisions.
3. Use a fresh pinned build to exercise the actual candidate dependency.
   Local overrides and installed packages can otherwise hide a bad pin.
4. Run both dependency matrices from the CLI root:

   ```sh
   python -B tests/check_core_dependency.py --shared ON
   python -B tests/check_core_dependency.py --shared OFF
   ```

   They build and test successful selection modes and check rejection cases.
   Do not use `--skip-git` as evidence that the new Git pin works. Retain the
   generated logs and `summary.json`; report which platforms were checked.
5. Run contributor checks and review behavioral differences. Preserve the
   frozen migration baseline; never regenerate expected observations from
   the candidate to make a failure pass. Intentional CLI behavior changes
   require explicit tests and documentation.
6. Before releasing, require the hosted Windows/Linux, shared/static release
   gate for the exact merged CLI commit. See [release validation](releases.md#request-a-release).

JSON pin updates follow the same validation discipline and also require
updating its exact package version and local-source requirements consistently.

## Development builds and releases

`Release` is a compiler configuration; it does not make a build an official
CLI release. Normal CLI versions derive from this repository's Git history
and tags, independently of Core. Local source overrides deliberately allow
other Core revisions without changing the CLI version.

The [release guide](releases.md) is authoritative for version formats,
prereleases, clean candidate builds and the release workflow. The gate checks
the exact CLI commit and pinned Core/JSON revisions on both platforms and
linkages before creating a new CLI tag. Candidate version overrides are
reserved for that workflow. It publishes tested executable archives with
checksums and attestations. See the [quality gate policy](quality-gates.md)
for Core artifact selection and the release activation prerequisite.

## Troubleshooting

| Symptom | Check or action |
| --- | --- |
| Core checkout path is missing | Correct the explicit override or clone the sibling before using `workspace`; no fallback occurs for a bad explicit path |
| Expected the Git pin but a package was selected | Use a fresh pinned build with `FETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER` and no source overrides |
| Missing `OpenTLV::tlv++` or legacy `tlvpp` export | Select a compatible Core revision/package with the public targets and C++ facade enabled |
| Required Core capability rejected at compile time | Enable the required public components in the source build or choose a compatible installed package |
| Offline configure attempts a download | Supply both Core and JSON sources/packages; check paths and JSON's exact package version |
| Version generation rejects a shallow clone | Obtain complete CLI history and tags, for example with `git fetch --unshallow --tags` while online |
| CTest cannot find the executable | Build first and use the same directory/configuration; Visual Studio Debug needs `-C Debug` |
| CTest reports no tests | Configure with `OPENTLV_CLI_BUILD_TESTS=ON`, build, and use the correct test directory |
| Runtime cannot load a shared Core library | In build trees the CLI prepares Windows DLL placement; for deployment follow the [installation notes](../README.md#install) and provide the installed Core runtime on the platform's library search path |
| Generator/compiler mismatch after reconfiguration | Use a fresh directory for the new generator/compiler and dependency mode |

CLI owns these documentation sources. The independent OpenTLV Docs
infrastructure assembles and publishes documentation; Core owns the native
APIs and generic processing semantics.
