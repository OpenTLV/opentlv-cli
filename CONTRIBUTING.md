# Contributing to OpenTLV CLI

Keep changes focused on the CLI application. Generic processing, public APIs,
and shared semantic tests belong to [Core](https://github.com/OpenTLV/opentlv).
The extraction must preserve commands, arguments, exit codes, stdout, stderr,
diagnostics, and the executable name `otlv`.

This guide adds CLI-specific build, test and provenance rules to the shared
[OpenTLV contribution guidelines](https://github.com/OpenTLV/.github/blob/main/CONTRIBUTING.md).
All project spaces follow the
[Code of Conduct](https://github.com/OpenTLV/.github/blob/main/CODE_OF_CONDUCT.md).
Report suspected vulnerabilities privately through this repository's Security
tab as described in the
[security policy](https://github.com/OpenTLV/.github/blob/main/SECURITY.md),
not in public issues. The [support directory](https://github.com/OpenTLV/.github/blob/main/SUPPORT.md)
lists the owning repository for each component.

## Development

Follow the [development guide](docs/development.md) for standalone and
workspace builds, presets, Debug/Release configurations, offline requirements,
dependency troubleshooting and the Core pin update procedure.
Run CTest for the dependency smoke tests, original CLI suites, Query facade,
and frozen migration comparison. Run the shared/static dependency matrix in
[tests/README.md](tests/README.md) before changing dependency integration.
Supply both Core and nlohmann/json sources or packages for offline builds.

Use a local `feature/<issue>_<description>` branch. Include the relevant issue
in the pull request and complete the [template](.github/PULL_REQUEST_TEMPLATE.md).
Describe local checks separately from hosted CI and release validation.

Consume Core only through its public CMake targets and APIs. Follow the
[release guide](docs/releases.md) for independent CLI versioning and validation.
Do not add dependency shims,
package-manager publishing, or placeholder CLI behavior.

## Contributor tools

Install tools in a dedicated virtual environment so other Python environments
and component tools remain unaffected. Use Python 3.10 or newer.

```sh
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` on PowerShell or
`source .venv/bin/activate` in Bash, then run:

```sh
python -m pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
```

The first hook run downloads pinned environments and needs network access.
Hooks check whitespace, YAML/JSON/Python syntax, file sizes, C/C++ formatting,
Markdown, and REUSE license metadata. Stage intended new files before running
`--all-files`; Git does not include untracked files in that selection.
Hooks can fix formatting, so review the resulting diff.

`.clang-format` follows the Core C++ style. Keep text files in LF format.
Binary fixtures (`.bin`, `.dat`, and `tests/fixtures/binary/`) are excluded
from text rewriting.

## License and provenance

The CLI is MIT licensed. Marek Cingel holds copyright in his original
contributions, including the CLI migrated from Core; other contributors retain
copyright in theirs, since an MIT contribution does not assign copyright.
OpenTLV is a GitHub organization, not a copyright holder. Preserve existing
notices. Original source files by Marek Cingel use:

```cpp
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel
```

Use the corresponding comment syntax in CMake, Python, JavaScript and other
languages, and your own name and year for your own work. Do not apply this
example to someone else's work or rewrite third-party notices.
Configuration, documentation and immutable migration snapshots are enumerated
explicitly in `REUSE.toml`; do not add headers to frozen snapshots. Add
explicit entries or `.license` sidecars for new files that cannot carry
comments. `LICENSES/` supplies the license texts referenced by SPDX metadata.

Executable packages carry `licenses/OpenTLV-CLI.txt` (this `LICENSE`),
`licenses/OpenTLV.txt` (the Core license) and `licenses/nlohmann-json.txt`.
Add the license text of every new bundled or linked dependency to the package
in `scripts/cli_build.py`.

The [changelog](CHANGELOG.md) records the baseline Core SHA and preceding tag.
The [migration manifest](tests/migration.json) records the imported files and
fixture revisions. Preserve original notices and regression provenance without
importing Core Git history. Shared Core tests and canonical fixtures remain in
Core; CLI tests consume immutable snapshots. The frozen baseline is historical
evidence: do not regenerate `tests/baseline/expected.json` from a candidate.

## Changelog

Document meaningful changes under `Unreleased`. Prepend each entry to its
existing Keep a Changelog category; create a missing category immediately
below `Unreleased`. Keep each entry on one line, include issue references,
and do not use pull-request numbers. Preserve released history.

## Validation

For dependency changes, run the shared and static integration matrix,
pre-commit checks, `python -B scripts/check_static.py` (requires cppcheck 2.13+),
and `git diff --check`. Follow the Core-aligned
[quality gates](docs/quality-gates.md): Linux PR checks, lightweight Main smoke,
manual Full verification and independent exact-commit Release validation.
Full CI runs every dependency scenario on both platforms and linkages.
Keep the original suites alongside the 153 unchanged baseline observations and
the explicit issue #4 version expectation. A build or dependency smoke-test
pass alone does not establish command parity. State missing coverage explicitly.
