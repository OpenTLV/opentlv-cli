# Changelog

All notable changes to OpenTLV CLI will be documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
CLI releases will be versioned independently from Core.

## [Unreleased]

### Fixed

- Remove the OpenTLV organization, inherited from the GitHub template, as a copyright holder from `LICENSE` and the README, leaving Marek Cingel to match the source headers and the Core license; packages built from this revision carry the corrected `OpenTLV-CLI.txt`. (#21)
- Retry delayed GitHub Actions job timing metadata for the same run attempt before generating a CLI timing report, rejecting persistently incomplete data. (OpenTLV/opentlv#638)
- Accept trailing CMake comments when validating immutable dependency SHAs in the CLI release gate, while rejecting duplicate or malformed pins. (#4, OpenTLV/opentlv-docs#21)

### Changed

- Normalize CLI licensing and community policies to the Workspace reference: annotate `REUSE.toml` itself, list its configuration, documentation and frozen migration snapshot paths explicitly, document copyright attribution and packaged license notices, and link the shared `OpenTLV/.github` contribution, conduct, security and support policies from the contributor guide, README and local issue chooser. (#23)
- Align CLI Pull Request, lightweight Main, manual Full and Release gates with Core; verify Core artifact identity and provenance, publish tested executable archives with checksums and attestations, and retain exact-commit evidence and CI timings. (OpenTLV/opentlv#638)
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
