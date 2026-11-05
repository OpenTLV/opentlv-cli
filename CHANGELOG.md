# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add CLI sanitizer configurations for Unix ASan/UBSan and Windows MSVC ASan with instrumented static Core, focused executable/security regressions, symbolized detector self-checks and retained failure logs in Full CI; cover bounded argument, input, JSON ownership and output-path failures without running Core tests or fuzzing. (#16)
- Add executable-focused CTest regressions for every command family, argument errors, exit codes, separate output streams, diagnostics, JSON structure and escaping, file handling, generation and shell completions; require the suite in release evidence. (#15)
- Generate GitHub Dependency Graph snapshots for OpenTLV Core and nlohmann_json from successful Main builds, evaluated CMake target links and immutable build pins; submit with a separate Main-only permission boundary and retain request/response diagnostics. (#14)

### Fixed

- Pass the clang-tidy check set explicitly (`-*,clang-diagnostic-*,clang-analyzer-*`, the previous built-in default) so clang-tidy 22 on Ubuntu 26.04 no longer stops with "no checks enabled", and fail with a clear message if the installed clang-tidy provides no Clang Static Analyzer checks. (#13)

### Changed

- Package the Linux and Windows executables already tested by the release's Full CI, then attest those same bytes without rebuilding. Keep Core tests, fuzzing, benchmarks and JSON tests disabled in every CLI source-consumption mode; cache authenticated Core downloads and contributor tools without reusing verification results or build trees. (#14)
- Require ISO C++23 without compiler extensions for every CLI-owned C++ target: the standard is set after Core is added, `otlv` requires `cxx_std_23` and builds MSVC with `/permissive-`, and the new `src/cxx_requirements.cpp` fails the build when a flag selects an older standard or a GNU dialect. Core remains C99 with a C++11 public C++ facade. (#13)
- Support GCC 15, Clang 22, AppleClang 17 (Xcode 26) and MSVC 19.50 (Visual Studio 2026) as the minimum CLI compilers; configuration warns for older or other compilers, and the development guide documents the policy. (#13)
- Move every CLI CI job that compiles or analyzes C++ to the current stable hosted toolchains with explicit compilers: PR builds, clang-tidy, CodeQL and sanitizers use Clang 22 on Ubuntu 26.04; Full, Main smoke, the dependency matrix and Linux packages use GCC 15 on Ubuntu 26.04; Windows uses Visual Studio 2026 on Windows Server 2025, and macOS uses Xcode 26 on macOS 26. cppcheck analyzes C++23, clang-format parses the latest standard, and the release gate requires C++23 dependency evidence. Linux packages now need the glibc and libstdc++ of Ubuntu 26.04 or newer, and Windows packages need the Visual Studio 2026 C++ runtime or newer. (#13)

- Link OpenTLV Core statically into `otlv` on Windows, Linux and macOS as the only supported linkage: local sibling sources and the pinned FetchContent fallback build static Core without changing `BUILD_SHARED_LIBS`, compatible installed static Core packages remain supported, and `OPENTLV_BUILD_SHARED_LIBS=ON` or a shared-only Core installation fails at configure time with remediation guidance. Core's own linkage policy is unchanged. (#12)
- Remove the shared/static Core linkage axis and the `--shared` option from CLI CI, dependency checks and release packaging; packages contain the executable without a Core runtime, release evidence records `core_linkage: static` for one Linux and one Windows x64 package, and the Core DLL copy and install RPATH are gone. (#12)
- Verify static Core linkage in every CLI build with the new `cli_static_core` CTest entry, which reads ELF, PE and Mach-O shared-library imports without platform tools, also checks relocated release packages, and runs in PR, Main smoke, Full and Release; Full CI adds a macOS Release build and test of the CLI. (#12)

## [0.2.0] - 2026-10-28

### Fixed

- Accept changelog versions without the Git tag prefix and publish release notes from the selected release section. (#25)
- Remove the OpenTLV organization, inherited from the GitHub template, as a copyright holder from `LICENSE` and the README, leaving Marek Cingel to match the source headers and the Core license; packages built from this revision carry the corrected `OpenTLV-CLI.txt`. (#21)
- Retry delayed GitHub Actions job timing metadata for the same run attempt before generating a CLI timing report, rejecting persistently incomplete data. (OpenTLV/opentlv#638)

### Changed

- Prepare CLI 0.2.0 against Core v0.8.0 at `345c77acb29266036df5f27d04ce315bb61853cc`, enabling authenticated Core binary or Verified Source consumption. (#25)
- Normalize CLI licensing and community policies to the Workspace reference: annotate `REUSE.toml` itself, list its configuration, documentation and frozen migration snapshot paths explicitly, document copyright attribution and packaged license notices, and link the shared `OpenTLV/.github` contribution, conduct, security and support policies from the contributor guide, README and local issue chooser. (#23)
- Align CLI Pull Request, lightweight Main, manual Full and Release gates with Core; verify Core artifact identity and provenance, publish tested executable archives with checksums and attestations, and retain exact-commit evidence and CI timings. (OpenTLV/opentlv#638)

## [0.1.0] - 2026-10-18

### Fixed

- Accept trailing CMake comments when validating immutable dependency SHAs in the CLI release gate, while rejecting duplicate or malformed pins. (#4, OpenTLV/opentlv-docs#21)

### Changed

- Make Bash `pipefail` explicit in both quality-check steps so failures propagate through `tee` while preserving artifact logs. (#4)
- Report an independent Git-derived CLI version through `otlv --version`; retain the frozen migration evidence with an explicit version-contract change. (#4)

### Added

- Notify the central documentation portal after a successful CLI release gate using the exact released tag, commit and validation attempt, independently of Core releases. (OpenTLV/opentlv-docs#21)
- Document standalone and workspace development, CMake presets, dependency selection, offline builds and Core revision updates. (#5)
- Add fast development CI and a complete Windows/Linux release gate that records pinned revisions and test evidence before creating the requested CLI tag. (#4)
- Migrate `otlv`, command documentation, original CLI regression suites and immutable Core fixture snapshots into the standalone repository, preserving command behavior against the frozen 154-case baseline. (#3)
- Add Git fallback isolation checks that bypass discoverable local Core packages and verify the pinned checkout revision and the source provenance of both public CMake targets. (#2)
- Resolve Core through an explicit local source override, installed public CMake targets, or a pinned Git fallback; add standalone/workspace presets and Windows/Linux dependency integration checks for shared and static builds. (#2)
- Bootstrap the standalone CLI repository with an independent CMake project, source/test layout, development instructions, formatting and pre-commit checks, and GitHub contribution templates; preserve the executable name `otlv` for the subsequent implementation migration. (#1)
- Record the CLI migration baseline origin as OpenTLV Core commit `e9cbb29897652fa75753ea89459e3f5e26671d3a`; the nearest preceding tag is `0.7.1` at `e12a52ff69a64468eecab084795a0530c273efea`, 11 commits before that origin. The baseline is from the origin SHA, not the tag; no CLI implementation or Core Git history is imported by this bootstrap. (#1)
