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

The [Core-aligned quality gates](quality-gates.md) separate Linux Pull Request
validation, lightweight Main integration, manual Full CI and release publication.
PR and Full require formatting, static analysis and CodeQL. Main runs only
a build and narrow integration smoke checks.

Cppcheck analyzes CLI sources, including conditional command implementations;
it uses normal checking depth to keep development checks fast and does not
analyze Core or JSON internals. The compiler validates
`core_requirements.cpp`, whose sole purpose is rejecting unsupported Core
configurations. Its deliberate `#error` paths are excluded from cppcheck.

The full dependency-resolution matrix runs in Full CI and release validation.
Run it locally when changing dependency selection or runtime linkage, as
described in [the test guide](../tests/README.md).

## Request a release

Select a published Core release with the #637 schema-2 artifacts and update
the matching Core SHA and `cmake/core-artifact.json` lock. An unset artifact
release is development-only and blocks CLI release.

Close the changelog before merging the release candidate: its first release
heading must be `## [v0.2.0] - YYYY-MM-DD`, match the requested tag, contain
changes and have a valid date. No `Unreleased` text may remain. During ordinary
development keep the normal `Unreleased` section. Preserve historical releases.

Run **CLI release gate** from `main`, supplying only a new `tag`, for example
`v0.2.0`. The dispatch SHA is the locked candidate; there is no alternate commit
or skip-verification input. Do not create the tag in advance.

The workflow:

1. Verifies the dispatch commit, closed changelog and new version tag on `main`.
2. Locks CLI/Core/JSON/workflow SHAs, the Core artifact policy, version, run and attempt.
3. Runs Full CI for the exact CLI SHA: platform/linkage and dependency scenarios,
   CLI suites, sanitizers, static analysis and CodeQL. Core suites are not repeated.
4. Authenticates Core artifacts, builds and tests CLI executables, then validates
   their archives after extraction into a separate location.
5. Rejects incomplete, failed, skipped or stale evidence and mismatched artifacts.
6. Generates SHA-256 checksums and attestations, verifies every producer identity,
   creates the tag and publishes the GitHub Release. Tags/assets are not replaced.
   The portal-compatible result is uploaded after successful publication.

Candidate builds use `OPENTLV_CLI_CANDIDATE_VERSION` together with
`OPENTLV_CLI_CANDIDATE_SHA`. CMake accepts this pair only for the exact clean
CLI checkout. This lets the workflow test the future release output without
creating a tag before validation. Normal builds derive versions from Git.
Neither the source nor changelog is rewritten by the workflow.

Validation jobs have read-only repository permissions and checkout credentials
are not persisted. Only the final job can create the tag; its gate code comes
from the trusted workflow revision. CLI releases are serialized, including requests
for different tags, because one commit must not receive multiple version tags.
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
  per-matrix summaries and their SHA-256 hashes, build and test counts, exact
  Full CI evidence and package records.
- `cli-quality-full-<sha>-<attempt>`: exact revision, job results and configuration.
- `release-binary-<platform>-<linkage>-<attempt>`: tested archives and build records.
- GitHub Release assets: four CLI archives and their JSON records,
  `release-manifest.json` and `SHA256SUMS`, all with producer attestations.

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

Package-manager publishing remains outside this scope. Local checks and synthetic
tests do not establish hosted release readiness; the new artifact path requires
a controlled hosted release. A publication-service failure can leave a tag without
a release or a partial release. Inspect and recover manually; a new dispatch
rejects an existing tag.

## Documentation publication

After a successful **CLI release gate**, **Notify CLI documentation portal**
sends the exact CLI tag, released commit, gate run ID and attempt to
`OpenTLV/opentlv-docs`. The notifier reads `release-result-<attempt>` from that
run; it does not check out or execute candidate code. The gate's workflow
commit equals the locked release SHA in the new workflow; historical evidence
with distinct workflow/candidate commits remains readable. Notification is a separate workflow: a documentation failure does
not undo the CLI tag or change the gate result.

The portal independently verifies the successful gate and its release
evidence, resolves the tag and publishes CLI-owned `docs/` at
`https://opentlv.github.io/opentlv-docs/cli/<version>/`.
CLI documentation has its own version selector and stable alias. Core and
Docs version numbers do not determine CLI documentation versions. Prerelease
tags are published under their own versions without replacing CLI stable.
Existing release snapshots remain unchanged when the portal layout evolves.

Repository setup requires `OPENTLV_DOCS_DISPATCH_TOKEN`, scoped to dispatching
events to `OpenTLV/opentlv-docs`, and the receiver workflow merged in Docs.
Docs also needs `OPENTLV_CLI_READ_TOKEN` with read access to CLI workflow
artifacts and repository metadata to verify the release independently.
See the [portal publication guide](https://github.com/OpenTLV/opentlv-docs#independent-cli-release-publication)
for permissions, activation and provenance checks. The cross-repository
credential is available only to the notifier's API step.

If notification fails, rerun **Notify CLI documentation portal** for the same
successful gate; do not rerun the gate to recreate an existing tag. Repeated
notifications safely reuse the existing documentation snapshot. Preserve the
release evidence artifacts for retries: missing or expired evidence fails
verification. Verify the notifier, Docs workflow and published snapshot
separately before claiming production documentation publication succeeded.
