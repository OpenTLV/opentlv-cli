# CLI versions and releases

OpenTLV CLI has its own Git tags and changelog. Core release timing does not
determine CLI versions. The executable remains `otlv`.

## Version reporting

```text
otlv --version
OpenTLV CLI 0.1.0
```

CLI release tags use `vMAJOR.MINOR.PATCH`, optionally with a SemVer prerelease
such as `v0.1.0-rc.1`. Numeric identifiers cannot have leading zeroes. Tag build
metadata is not supported. The `v` prefix distinguishes CLI tags from the
historical Core convention. Use a checkout with full history and tags.
Shallow clones fail explicitly. Each release uses a distinct commit with one
CLI version tag; multiple version tags on the same commit are ambiguous and
rejected. This also applies when promoting a prerelease to a stable release.

The version is generated from the CLI repository at configure and build time:

| Checkout | Reported version example |
| --- | --- |
| Exact clean `v0.1.0` tag | `0.1.0` |
| Exact clean `v0.1.0-rc.1` tag | `0.1.0-rc.1` |
| Two commits after `v0.1.0` | `0.1.0-dev.2+g0123456789ab` |
| Two commits after `v0.1.0-rc.1` | `0.1.0-rc.1.dev.2+g0123456789ab` |
| No CLI tags | `0.0.0-dev.<commit-count>+g<sha>` |
| Dirty checkout | Git metadata ends in `.dirty` |
| Source export without its own Git repository | `0.0.0+unknown` |

The enclosing project's tags and the Core dependency's tags are never used.
Changing Core does not change the CLI version. Rebuilding refreshes metadata;
an unchanged generated header does not cause recompilation. Untracked files
count as dirty unless ignored. Source exports intentionally do not claim a
release version.

Issue #4 intentionally replaces the old `otlv <Core-version>` output. The
historical migration baseline is unchanged: the current test driver compares
153 observations exactly and verifies the version observation against the
new contract, including empty stderr, exit zero and no output files.

## Development checks

Use the [development guide](development.md) for local builds, dependency
selection and Core pin updates. The CMake `Release` configuration controls
compiler settings; it does not establish an official CLI release. Normal
development builds derive their version from Git even when built in Release.

Pull requests and pushes to `main` run Windows/MSVC static and Linux/GCC shared
builds, pinned dependency selection, all applicable command and tooling tests,
pre-commit checks and cppcheck. They upload CTest XML, baseline and Query
reports. The quality job records the static analyzer version and logs.

Cppcheck analyzes CLI sources, including conditional command implementations;
it uses normal checking depth to keep development checks fast and does not
analyze Core or JSON internals. The compiler validates
`core_requirements.cpp`, whose sole purpose is rejecting unsupported Core
configurations. Its deliberate `#error` paths are excluded from cppcheck.

The full dependency-resolution matrix is reserved for release validation.
Run it locally when changing dependency selection or runtime linkage, as
described in [the test guide](../tests/README.md).

## Request a release

Merge the intended source, documentation and changelog changes first. Obtain
the full 40-character CLI commit SHA. Run **CLI release gate** from `main`,
supplying that SHA as `commit` and a new tag such as `v0.1.0` as `tag`.
These versions are examples, not an automatic first-release choice.

The workflow:

1. Verifies that the requested object is exactly that commit and is an ancestor
   of the trusted workflow revision on `main`. Rejects malformed/existing tags.
2. Reads the immutable Core and JSON pins from that commit. The request records
   those SHAs, CLI SHA, workflow SHA, requested version, run ID and attempt.
3. Checks out the exact CLI SHA on Windows and Linux, for static and shared
   Core. Each job fetches and verifies the pinned dependencies, exercises all
   successful and rejected dependency scenarios, and runs every required test.
4. Runs the same formatting, license, syntax and static checks on the candidate.
5. Aggregates all four matrix reports and rejects missing/duplicate scenarios,
   dirty or mismatched revisions, stale runs, failed tests and unexpected skips.
6. Uploads the validation report, then creates the requested tag at the tested
   SHA only when validation and quality jobs succeeded. It never moves a tag.

Candidate builds use `OPENTLV_CLI_CANDIDATE_VERSION` together with
`OPENTLV_CLI_CANDIDATE_SHA`. CMake accepts this pair only for the exact clean
CLI checkout. This lets the workflow test the future release output without
creating a tag before validation. Normal builds derive versions from Git.
Neither the source nor changelog is rewritten by the workflow.

Validation jobs have read-only repository permissions and checkout credentials
are not persisted. Only the final job can create the tag; its gate code comes
from the trusted workflow revision. Concurrent requests for a tag are serialized.
If another actor creates the tag during validation, create-only publication
fails instead of replacing it. Repository tag rules must allow the workflow
token to create the requested tag; a policy rejection leaves validation
evidence available and does not create a release.

## Release evidence

- `release-request-<attempt>`: CLI/Core/JSON/workflow SHAs, version, run ID and attempt.
- `release-evidence-<attempt>-<platform>-<linkage>`: per-command logs, CTest XML,
  configured versions, baseline/Query reports and a matrix summary with
  compiler identity, architecture, C++ standard and Release configuration.
- `cli-quality-<attempt>`: formatting/license and static-analysis logs.
- `release-result-<attempt>`: aggregate validation status, required job outcomes,
  per-matrix summaries and their SHA-256 hashes, build and test counts.

Each successful dependency scenario runs 11 CTest entries, 154 CLI behavior
cases (153 original plus the independent version contract), and 338 Query
backend checks. The two named external fixture-provider exclusions are
recorded explicitly. Release validation covers five successful build modes
and six expected configuration rejections per platform/linkage: 20 builds
and 220 passing CTest entries across the complete matrix. Counts describe
different test layers and must not be added together.

Failure logs are uploaded even when a matrix job fails. Missing evidence
cannot be promoted to a passing result. A passing validation report records
validation; tag creation is confirmed separately by the workflow's final step
and job summary. Download artifacts for durable retention as required by your
release process; GitHub's configured artifact retention still applies.
Retry with **Re-run all jobs** or a new dispatch. Evidence from a previous
attempt is never reused; rerunning only failed jobs cannot authorize a release.

This workflow creates a Git tag only. Binary archives, package-manager
publishing and binary distribution remain outside this migration. Local
checks and synthetic gate tests do not establish hosted release readiness;
the first real release still needs a successful hosted workflow and tag step.
