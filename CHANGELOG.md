# Changelog

All notable changes to OpenTLV CLI will be documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
CLI releases will be versioned independently from Core.

## [Unreleased]

### Added

- Bootstrap the standalone CLI repository with an independent CMake project, source/test layout, development instructions, formatting and pre-commit checks, and GitHub contribution templates; preserve the executable name `otlv` for the subsequent implementation migration. (#1)
- Record the CLI migration baseline origin as OpenTLV Core commit `e9cbb29897652fa75753ea89459e3f5e26671d3a`; the nearest preceding tag is `0.7.1` at `e12a52ff69a64468eecab084795a0530c273efea`, 11 commits before that origin. The baseline is from the origin SHA, not the tag; no CLI implementation or Core Git history is imported by this bootstrap. (#1)
