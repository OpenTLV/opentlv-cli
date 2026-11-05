# CLI quality gates

This repository follows Core #637/#642's PR, Main, Full and Release architecture.
CLI owns command parsing, stdout/stderr, exit codes, files, diagnostics, process
lifecycle and executable distribution. Core owns comprehensive library semantics,
native unit suites, properties, fuzzing, ABI, benchmarks and Callgrind. CLI never
starts Core Full CI or imports those suites. Shared Query corpus snapshots are
exercised through CLI processes to verify the facade contract.

## Entry points

| Workflow | Trigger | Required verification |
| --- | --- | --- |
| `cli-pr.yml` | PR targeting `main` | Linux Clang 22 Debug CLI, all 14 CTest entries including executable regressions and the static Core linkage check, pre-commit, cppcheck, clang-tidy, tooling regression tests and CodeQL |
| `cli-main.yml` | Push to `main` | One Linux GCC 15 build, C/C++ linkage, static Core linkage and CLI version smoke; submit resolved dependency snapshot |
| `cli-full.yml` | Manual or reusable release call | Linux/GCC 15, Windows/MSVC (Visual Studio 2026) and macOS/AppleClang (Xcode 26) Release; all CLI suites; complete dependency selection matrix on Linux and Windows; Linux Clang 22 Debug ASan/UBSan with leak detection and Windows MSVC Debug ASan; all static checks and CodeQL |
| `release.yml` | Manual from `main`, only `tag` | Closed changelog, locked dispatch SHA and dependencies, same-attempt Full CI, validated CLI packages, SHA-256, producer attestations, tag and GitHub Release |

Full CI has no push or scheduled trigger. PR checks have no branch-push trigger.
Main does not repeat PR static analysis or the full test matrix. Release repeats
Full independently for its exact candidate; historical PR results cannot replace
it. Within that release attempt, Full's Linux/Windows/macOS workers package their
already-tested executables and verify the relocated archives. The `binaries`
job downloads those exact artifacts and attests them after Full succeeds; it
does not configure, download dependencies, compile or repeat the build tests.
The separate relocation baseline still verifies packaging. Standalone Full CI
never publishes or packages. The CLI is compiled as ISO C++23 with
the [supported compilers](development.md#language-standard-and-compilers);
Core's public C++ consumption requirement remains C++11 and is not retested.

The always-running aggregate gate rejects missing, failed, cancelled and
unexpectedly skipped jobs. Only declared Full-only jobs may be skipped in PR CI.
Full evidence records the repository, exact SHA, run, attempt, worker definitions
and hashes of build/configuration helpers. Actual build records also identify
compiler, configuration, dependencies and test results. Core native tests are
disabled at the CLI's Core consumption boundary, including dependency-selection,
static-analysis and local source builds. Directory-scoped settings also disable
Core examples, benchmarks, property tests and fuzzing, plus JSON's own tests.
They do not change Core's standalone configuration. The Full sanitizer job uses
two focused configurations: Linux Clang ASan/UBSan
and Windows MSVC ASan. Each runs the maintained executable suite, bounded security
cases, static-linkage/version checks and detector self-checks. It does not repeat
the migration baseline, Query corpus or Core suites. PR and Main add no sanitizer
builds; all ordinary regression builds include the security cases.

The full dependency runner retains five successful build modes and eight rejected
configurations per platform. These test CLI's CMake consumption contract;
they do not repeat Core verification. See the [test inventory](../tests/README.md).

## Core dependency policy

`cmake/Core.cmake` pins one full Core SHA. `cmake/core-artifact.json` must agree
with it and names an optional published Core release. An unset release tag means
**pinned Git development source**, never Verified Source; release preflight
rejects an unset tag. CLI `0.2.0` locks the published Core `v0.8.0` release at
`345c77acb29266036df5f27d04ce315bb61853cc`, whose schema-2 manifest, binary
packages and Verified Source archive activate authenticated consumption.

Update both pins deliberately and validate the complete CLI matrix. The consumer:

1. Resolves the named Core release and requires its tag to match the locked SHA.
2. Downloads the schema-2 manifest and SHA256SUMS and verifies both GitHub
   attestations against `OpenTLV/opentlv`, `core-release.yml` and that SHA.
   Release preflight also locks the Core release ID and authenticated manifest
   digest; publication rejects replacement assets or a changed release identity.
3. Checks manifest identity, Full CI/candidate linkage and archive digests.
4. Prefers a verified binary only when OS, x64 architecture, compiler version,
   Release configuration, linkage and libc/MSVC runtime match the local probe.
5. Uses the separately attested Verified Source archive when no compatible binary
   exists and `allow_verified_source` is true. Debug/sanitizer configurations use
   source. An authentication or checksum failure always stops verification.
6. Extracts contained files safely and builds through public `OpenTLV::tlv` and
   `OpenTLV::tlv++` targets. Explicit binary selection cannot fall back to Git.

GitHub's automatic source archives are not substitutes for the named Verified
Source artifact. SHA-256 alone does not authenticate its producer. Verification
requires `gh` with read access to Core release assets and attestations. There is
no release input for disabling verification or selecting a different commit.

The JSON dependency retains its independent immutable Git pin and license.
Local developer source overrides remain available; build evidence marks them as
unverified and release builds reject them.

## Dependency Graph and permissions

After Main's smoke checks succeed, a separate `dependencies` job consumes only
that run's SHA/attempt-qualified build evidence. `scripts/dependency_snapshot.py`
checks repository, commit, run, attempt, successful smoke results and dependency
pins before calling the [GitHub Dependency Submission API](https://docs.github.com/en/rest/dependency-graph/dependency-submission).
Submission failures fail the Main gate; the snapshot and API response (when
available) are retained as `cli-dependency-submission-<sha>-<attempt>` artifacts.
A 403 requires checking repository Dependency Graph availability and Actions
token policy; no personal access token is needed by the workflow.

`cmake/Dependencies.cmake` observes actual target links for the selected
configuration, including the header-only C++ facade and JSON library.
Build verification checks JSON's clean checkout and exact SHA, and Core's
pinned checkout or authenticated artifact identity. Package URLs use origins
and full revisions from `cmake/Core.cmake` and `cmake/Json.cmake`, without a
second dependency manifest. Both packages are direct runtime dependencies:
their code is incorporated into the executable. Core's C and C++ targets belong
to the same package; there is no Core-to-JSON edge.

The current selected targets have no external transitive package dependencies.
An unknown target/link edge stops snapshot generation with its target and link
name; extend discovery and identity verification when adding such a dependency.
This avoids guessing package versions for system runtimes or publishing an
incomplete graph. Local Core overrides are not publishable evidence. A stable
detector/correlator replaces the previous Main snapshot; PRs, forks, Full and
releases never submit competing snapshots.

| Job | Additional token permissions | Purpose |
| --- | --- | --- |
| Ordinary build, dependency matrix, quality | None beyond `contents: read` | Read sources and Core assets |
| Main `dependencies` | `contents: write` | Dependency Submission API; no Git credentials persisted |
| CodeQL and its reusable callers | `security-events: write`, `actions: read` | Upload analysis and read workflow metadata |
| Timing jobs | `actions: read` | Read job timing metadata |
| Release signing | `id-token: write`, `attestations: write` | Attest tested packages |
| Release publisher | `contents: write`, `actions: read`, `id-token: write`, `attestations: write` | Verify, attest and publish the release |

Write access is isolated to the relevant jobs. Reusable callers pass CodeQL's
permissions through the call chain; ordinary workers retain `contents: read`.
No `pull_request_target` or privileged workflow consuming PR artifacts is used.

## Download caches

Main and ordinary Full/PR/sanitizer builds cache only Core archive downloads,
keyed by runner OS, build configuration and the Core artifact lock. A cache entry is a download
optimization, never verification evidence: each consumer fetches current
release metadata, rechecks the tag/commit, authenticates the manifest and
checksums, validates cached archive bytes by digest and verifies producer
attestations again. Changed/corrupt bytes fail with instructions to discard the
cache. No extracted package, CMake build tree or prior success is restored.

Quality caches pip downloads and pre-commit environments using the pinned
requirements/hook configuration. The full dependency-selection runner keeps
its real Git fallback test, then reuses those exact checked-out sources across
local/package/workspace scenarios. Release packaging reuses Full's completed
builds, avoiding another Core/JSON download and compilation on all release targets.

## Static Core linkage

Every CI build links OpenTLV Core statically; no workflow has a linkage matrix
axis and no runner offers a shared Core option. Each build checks linkage twice:
`cmake/Core.cmake` rejects a non-static `OpenTLV::tlv`, and the `cli_static_core`
CTest entry reads the executable's shared-library imports (ELF, PE or Mach-O)
and fails if any of them is an OpenTLV Core library. Build evidence records
`core_linkage: static`. Core's own linkage configurations and its test suites
are not run by CLI CI. The macOS Full build verifies static Core linkage and
the CLI suites and supplies the arm64 release package.

## Executable artifacts

The [release artifact policy](releases.md#release-artifact-policy) defines Linux
x64, Windows x64 and macOS arm64 archives, their exact five-file layout, supported
runtime dependencies and naming. All packages use static Core and the executable
already tested by Full CI. Native producers verify the relocated version, startup,
file encode/decode and invalid-input handling with five small smoke checks; they
do not repeat the full CLI regression baseline.

Publication reopens every archive and checks its inventory, actual binary target,
Core linkage, runtime imports, embedded build record and executable hash. It
requires successful native smoke evidence from all three producers, the existing
dependency evidence and same-attempt Full CI before creating SHA256SUMS and the
release manifest. Every published archive and JSON record has a producer
attestation, as do the manifest and checksum list. The publisher verifies them
against its workflow and commit before creating the tag and release.

The docs portal's `release-result-<attempt>/result.json` contract is preserved.
The existing notifier runs only after the complete release workflow succeeds.
No portal source or historical release evidence is rewritten.

## Performance and hosted acceptance

[Baseline data](ci-baseline.json) records actual successful pre-change PR, main
push and release job timestamps and URLs. Each new entry point uploads timings
after its required checks. If the Jobs API has not exposed completion metadata
yet, collection retries the same run attempt up to six times, five seconds apart.
CLI-scoped reports reject incomplete timing metadata after those retries.
Summarize baseline observations locally with:

```sh
python -B scripts/ci_timings.py --baseline docs/ci-baseline.json --output build/ci-baseline-summary.json
```

Report PR/Main/Full/Release separately. Job seconds are elapsed runner time,
not billed minutes. Execution span includes scheduling gaps between the first
start and last finish, but excludes initial queue time. Compare equivalent event,
test scope, runner, toolchain and cache cohorts; the broader new release cannot
be labelled faster or slower solely from a mismatched historical run.

Post-change hosted timings, all four entry points, real Core artifact consumption,
Dependency Graph visibility for both packages, OIDC signing and a controlled
release remain required acceptance evidence.
Local fixtures/builds do not establish these results. Configure required PR checks
and release-tag permissions in repository settings after hosted check names exist;
workflow code cannot prevent administrators from changing repository policy.

## Local checks

```sh
python -B -m unittest discover -s tests -p 'test_ci_*.py'
python -B tests/test_release.py
node --test tests/test_docs_notification.cjs
actionlint
pre-commit run --all-files
```

Normal CMake/CTest and the dependency selection runner remain documented in
the [development guide](development.md). See [CLI sanitizers](development.md#cli-sanitizers)
for local commands, supported modes, runtime requirements and failure diagnostics.
Full CI retains CTest output, deliberate-fault logs and Core verification evidence
per platform; a missing runtime or unsymbolized detector report fails the lane.
