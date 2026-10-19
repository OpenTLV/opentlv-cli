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
| `cli-pr.yml` | PR targeting `main` | Linux Clang Debug shared CLI, all 11 CTest entries, pre-commit, cppcheck, clang-tidy, tooling regression tests and CodeQL |
| `cli-main.yml` | Push to `main` | One Linux shared build, C/C++ linkage/version smoke and CLI version output |
| `cli-full.yml` | Manual or reusable release call | Linux/GCC and Windows/MSVC Release, shared/static; all CLI suites; complete dependency selection matrix; Linux Clang Debug ASan/UBSan with leak detection; all static checks and CodeQL |
| `release.yml` | Manual from `main`, only `tag` | Closed changelog, locked dispatch SHA and dependencies, same-attempt Full CI, validated CLI packages, SHA-256, producer attestations, tag and GitHub Release |

Full CI has no push or scheduled trigger. PR checks have no branch-push trigger.
Main does not repeat PR static analysis or the full test matrix. Release repeats
Full independently for its exact candidate; historical PR results cannot replace
it. Standalone Full CI never publishes. Public C++ consumption remains C++11.

The always-running aggregate gate rejects missing, failed, cancelled and
unexpectedly skipped jobs. Only declared Full-only jobs may be skipped in PR CI.
Full evidence records the repository, exact SHA, run, attempt, worker definitions
and hashes of build/configuration helpers. Actual build records also identify
compiler, configuration, dependencies and test results. Core native tests are
explicitly disabled in the ordinary CI build runner.

The full dependency runner retains five successful build modes and six rejected
configurations per platform/linkage. These test CLI's CMake consumption contract;
they do not repeat Core verification. See the [test inventory](../tests/README.md).

## Core dependency policy

`cmake/Core.cmake` pins one full Core SHA. `cmake/core-artifact.json` must agree
with it and names an optional published Core release. An unset release tag means
**pinned Git development source**, never Verified Source. As inspected on
2026-10-19, the latest published Core release `0.7.1` has no release assets;
the current CLI pin predates the new artifact producer. CLI release preflight
therefore rejects the current unset artifact release. This is an explicit
activation prerequisite, not a bypass or a claim of production verification.

When the first suitable Core release exists, update both pins deliberately and
validate the complete CLI matrix. The consumer:

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

## Executable artifacts

The initial packages are Linux x64 and Windows x64, each shared/static Core,
Release configuration. Windows uses the dynamic MSVC runtime. Packages contain
`bin/otlv`, the shared Core runtime when applicable, license notices and build
identity. They do not promise compatibility with all OS/runtime versions.
The archive is unpacked into a separate directory and the CLI version contract
and 154-case behavior baseline run against the relocated executable.

Publication checks all four package identities and hashes, the complete existing
dependency evidence and same-attempt Full CI before creating SHA256SUMS and the
release manifest. Every published archive and JSON record has a producer
attestation, as do the manifest and checksum list. The publisher verifies them
again against its workflow and commit before creating the tag and release.

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
OIDC signing and a controlled release remain required acceptance evidence.
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

Normal CMake/CTest and the shared/static dependency runners remain documented in
the [development guide](development.md). Sanitizer execution enables ASan/UBSan
and leak detection for CLI-owned process tests and the linked source dependency.
It does not run the Core sanitizer suite.
