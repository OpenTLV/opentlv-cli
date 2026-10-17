# Changelog

All notable changes to OpenTLV CLI will be documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
CLI releases will be versioned independently from Core.

## [Unreleased]

### Changed

- Make Bash `pipefail` explicit in both quality-check steps so failures propagate through `tee` while preserving artifact logs. (#4)
- Report an independent Git-derived CLI version through `otlv --version`; retain the frozen migration evidence with an explicit version-contract change. (#4)

### Added

- Add fast development CI and a complete Windows/Linux release gate that records pinned revisions and test evidence before creating the requested CLI tag. (#4)
- Migrate `otlv`, command documentation, original CLI regression suites and immutable Core fixture snapshots into the standalone repository, preserving command behavior against the frozen 154-case baseline. (#3)
- Add Git fallback isolation checks that bypass discoverable local Core packages and verify the pinned checkout revision and the source provenance of both public CMake targets. (#2)
- Resolve Core through an explicit local source override, installed public CMake targets, or a pinned Git fallback; add standalone/workspace presets and Windows/Linux dependency integration checks for shared and static builds. (#2)
- Bootstrap the standalone CLI repository with an independent CMake project, source/test layout, development instructions, formatting and pre-commit checks, and GitHub contribution templates; preserve the executable name `otlv` for the subsequent implementation migration. (#1)
- Record the CLI migration baseline origin as OpenTLV Core commit `e9cbb29897652fa75753ea89459e3f5e26671d3a`; the nearest preceding tag is `0.7.1` at `e12a52ff69a64468eecab084795a0530c273efea`, 11 commits before that origin. The baseline is from the origin SHA, not the tag; no CLI implementation or Core Git history is imported by this bootstrap. (#1)
