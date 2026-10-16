#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel

"""Exercise actual CLI CMake resolution, builds and runtime linkage in fresh directories."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, default=ROOT / "build/dependency-check")
    parser.add_argument("--core-source", type=Path, help="Core checkout for local/offline checks")
    parser.add_argument("--json-source", type=Path, help="nlohmann/json 3.11.3 checkout for offline checks")
    parser.add_argument("--skip-git", action="store_true", help="Skip real remote fallback; requires --core-source")
    parser.add_argument("--shared", choices=("ON", "OFF"), default="ON")
    parser.add_argument("--generator")
    args = parser.parse_args()
    if args.skip_git and (not args.core_source or not args.json_source):
        parser.error("--skip-git requires --core-source and --json-source")
    args.build_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="run-", dir=args.build_root.resolve()))
    print(f"Evidence: {work}", flush=True)
    results = []
    sequence = 0
    offline = os.environ.copy()
    # Git metadata commands still work, but an unintended HTTPS/SSH fetch fails.
    offline["GIT_ALLOW_PROTOCOL"] = "file"
    offline["GIT_TERMINAL_PROMPT"] = "0"
    common = [
        "-DCMAKE_BUILD_TYPE=Release",
        "-DOPENTLV_CLI_BUILD_TESTS=ON",
        f"-DOPENTLV_BUILD_SHARED_LIBS={args.shared}",
        "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
        "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF",
    ]
    if args.json_source:
        common.append(f"-DFETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON={args.json_source.resolve().as_posix()}")
    if args.generator:
        common += ["-G", args.generator]

    def run(*command, env=None, failure=None, cwd=ROOT):
        nonlocal sequence
        sequence += 1
        command = list(map(str, command))
        print("+ " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=cwd, env=env, text=True,
                                encoding="utf-8", errors="replace",
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = work / f"{sequence:02d}.log"
        log.write_text(result.stdout, encoding="utf-8")
        if failure:
            if result.returncode == 0 or failure not in result.stdout:
                raise RuntimeError(f"Expected failure containing {failure!r}: {log}\n{result.stdout[-6000:]}")
        elif result.returncode:
            raise RuntimeError(f"Command failed ({result.returncode}): {log}\n{result.stdout[-6000:]}")
        return result.stdout.strip()

    def configure(name, *options, env=None, failure=None):
        build = work / name
        run("cmake", "-S", ROOT, "-B", build, *common, *options,
            env=env, failure=failure)
        return build

    def check(build, expected, source=None, env=None, preset=None, cwd=ROOT):
        selection = (build / "tests/core-selection.txt").read_text(encoding="utf-8").splitlines()
        if selection[0] != expected:
            raise RuntimeError(f"{build}: expected {expected}, got {selection}")
        if source:
            source = source.resolve()
            if Path(selection[1]).resolve() != source:
                raise RuntimeError(f"{build}: selected wrong source: {selection}")
            if selection[4] not in ("FALSE", "0"):
                raise RuntimeError(f"{build}: C++ target must come from the source build")
            for target, origin in zip(("OpenTLV::tlv", "OpenTLV::tlv++"), selection[2:4]):
                if not origin or not Path(origin).resolve().is_relative_to(source):
                    raise RuntimeError(f"{build}: {target} originates outside {source}: {origin}")
        if preset:
            run("cmake", "--build", "--preset", preset, "--parallel", "2", env=env, cwd=cwd)
            run("ctest", "--preset", preset, env=env, cwd=cwd)
        else:
            run("cmake", "--build", build, "--config", "Release", "--parallel", "2", env=env)
            run("ctest", "--test-dir", build, "-C", "Release",
                "--output-on-failure", "--no-tests=error", env=env)
        baseline_path = build / "tests/Integration_cli_baseline-Release/baseline-report.json"
        query_path = build / "tests/query-cli-conformance-Release/query-report.json"
        # Single-config generators also use Release via CMAKE_BUILD_TYPE.
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        query = json.loads(query_path.read_text(encoding="utf-8"))
        if baseline["failures"] or len(baseline["observations"]) != 154:
            raise RuntimeError(f"Incomplete CLI baseline validation: {baseline_path}")
        if query["checks"] != 338 or len(query["exclusions"]) != 2:
            raise RuntimeError(f"Incomplete CLI Query validation: {query_path}")
        results.append({"case": build.name, "result": "passed", "mode": expected,
                        "baseline_cases": len(baseline["observations"]), "query": query})

    # A discoverable package that must never execute in forced fallback or source-override cases.
    trap = work / "package-trap"
    trap.mkdir()
    (trap / "OpenTLVConfig.cmake").write_text(
        'message(FATAL_ERROR "Package discovery must be bypassed in this test")\n',
        encoding="utf-8")

    core = args.core_source.resolve() if args.core_source else None
    if not args.skip_git:
        configure("fallback-package-trap", "-DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=ALWAYS",
                  f"-Dopentlv_core_DIR={trap.as_posix()}",
                  f"-DCMAKE_PREFIX_PATH={trap.as_posix()}", env=offline,
                  failure="Package discovery must be bypassed in this test")
        results.append({"case": "fallback-package-trap", "result": "passed (rejected)"})
        fallback = configure("git-fallback", "-DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER",
                             "-DCMAKE_DISABLE_FIND_PACKAGE_opentlv_core=ON",
                             f"-Dopentlv_core_DIR={trap.as_posix()}",
                             f"-DCMAKE_PREFIX_PATH={trap.as_posix()}")
        fetched = fallback / "_deps/opentlv_core-src"
        revision = run("git", "-C", fetched, "rev-parse", "HEAD")
        pin = re.search(r"GIT_TAG\s+([0-9a-f]{40})", (ROOT / "cmake/Core.cmake").read_text())[1]
        if revision != pin:
            raise RuntimeError(f"Fetched {revision}, expected {pin}")
        check(fallback, "source", fetched)
        if core is None:
            core = fetched
        if args.json_source is None:
            json_source = fallback / "_deps/nlohmann_json-src"
            json_pin = re.search(r"GIT_TAG\s+([0-9a-f]{40})", (ROOT / "cmake/Json.cmake").read_text())[1]
            if run("git", "-C", json_source, "rev-parse", "HEAD") != json_pin:
                raise RuntimeError("Fetched JSON does not match the migration pin")
            common.append(f"-DFETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON={json_source.as_posix()}")
    else:
        results.append({"case": "git-fallback", "result": "skipped"})

    local = configure("local-override",
                      f"-DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE={core.as_posix()}",
                      f"-DCMAKE_PREFIX_PATH={trap.as_posix()}",
                      "-DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=ALWAYS", env=offline)
    check(local, "source", core, env=offline)

    # Install the real library, then discover a separate, relocated copy.
    installed = work / "installed"
    relocated = work / "relocated package"
    run("cmake", "--install", local, "--config", "Release", "--prefix", installed, env=offline)
    shutil.copytree(installed, relocated)
    for config in relocated.rglob("*.cmake"):
        content = config.read_text(encoding="utf-8").replace("\\", "/")
        for private_path in (installed, local, core):
            if private_path.as_posix() in content:
                raise RuntimeError(f"Non-relocatable package: {config}")
    package = configure("installed-package", f"-DCMAKE_PREFIX_PATH={relocated.as_posix()}", env=offline)
    check(package, "package", env=offline)

    # A valid installed package must also lose to the explicit source override.
    priority = configure("override-before-package",
                         f"-DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE={core.as_posix()}",
                         f"-DCMAKE_PREFIX_PATH={relocated.as_posix()}", env=offline)
    check(priority, "source", core, env=offline)

    for name, targets in (
        ("missing-cxx", ["OpenTLV::tlv"]),
        ("legacy-cxx", ["OpenTLV::tlv", "OpenTLV::tlvpp"]),
        ("missing-core", ["OpenTLV::tlv++"]),
    ):
        fixture = work / name
        fixture.mkdir()
        (fixture / "OpenTLVConfig.cmake").write_text(
            "".join(f"add_library({target} INTERFACE IMPORTED)\n" for target in targets),
            encoding="utf-8")
        configure(name + "-build", f"-DCMAKE_PREFIX_PATH={fixture.as_posix()}",
                  env=offline, failure="Selected Core is incompatible")
        results.append({"case": name, "result": "passed (rejected)"})

    configure("cxx-disabled", f"-DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE={core.as_posix()}",
              "-DOPENTLV_BUILD_CXX=OFF", env=offline, failure="Selected Core is incompatible")
    results.append({"case": "cxx-disabled", "result": "passed (rejected)"})

    configure("invalid-source",
              f"-DFETCHCONTENT_SOURCE_DIR_OPENTLV_CORE={(work / 'absent').as_posix()}",
              f"-DCMAKE_PREFIX_PATH={relocated.as_posix()}", env=offline,
              failure="Manually specified source directory is missing")
    results.append({"case": "invalid-source", "result": "passed (rejected)"})

    # Presets must resolve from a checkout without sibling auto-discovery.
    preset_root = work / "preset workspace"
    cli_copy = preset_root / "opentlv-cli"
    cli_copy.mkdir(parents=True)
    for name in ("CMakeLists.txt", "CMakePresets.json", "cmake", "src", "tests"):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, cli_copy / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, cli_copy / name)
    run("git", "clone", "--no-hardlinks", "--", core, preset_root / "opentlv", env=offline)
    command = ["cmake", "--preset", "workspace", "-S", cli_copy, *common]
    run(*command, env=offline)
    preset_build = cli_copy / "build/workspace"
    check(preset_build, "source", preset_root / "opentlv", env=offline,
          preset="workspace", cwd=cli_copy)

    report = {
        "cli_revision": run("git", "rev-parse", "HEAD"),
        "cli_dirty": bool(run("git", "status", "--porcelain")),
        "core_revision": run("git", "-C", core, "rev-parse", "HEAD"),
        "core_dirty": bool(run("git", "-C", core, "status", "--porcelain")),
        "shared": args.shared,
        "results": results,
    }
    (work / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len([r for r in results if r['result'].startswith('passed')])} cases; "
          f"summary: {work / 'summary.json'}", flush=True)


if __name__ == "__main__":
    main()
