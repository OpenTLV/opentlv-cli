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
    parser.add_argument("--skip-git", action="store_true", help="Skip real remote fallback; requires --core-source")
    parser.add_argument("--shared", choices=("ON", "OFF"), default="ON")
    parser.add_argument("--generator")
    args = parser.parse_args()
    if args.skip_git and not args.core_source:
        parser.error("--skip-git requires --core-source")
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
        if source and Path(selection[1]).resolve() != source.resolve():
            raise RuntimeError(f"{build}: selected wrong source: {selection}")
        if preset:
            run("cmake", "--build", "--preset", preset, "--parallel", "2", env=env, cwd=cwd)
            run("ctest", "--preset", preset, env=env, cwd=cwd)
        else:
            run("cmake", "--build", build, "--config", "Release", "--parallel", "2", env=env)
            run("ctest", "--test-dir", build, "-C", "Release",
                "--output-on-failure", "--no-tests=error", env=env)
        results.append({"case": build.name, "result": "passed", "mode": expected})

    core = args.core_source.resolve() if args.core_source else None
    if not args.skip_git:
        fallback = configure("git-fallback", "-DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=NEVER")
        fetched = fallback / "_deps/opentlv_core-src"
        revision = run("git", "-C", fetched, "rev-parse", "HEAD")
        pin = re.search(r"GIT_TAG\s+([0-9a-f]{40})", (ROOT / "cmake/Core.cmake").read_text())[1]
        if revision != pin:
            raise RuntimeError(f"Fetched {revision}, expected {pin}")
        check(fallback, "source", fetched)
        if core is None:
            core = fetched
    else:
        results.append({"case": "git-fallback", "result": "skipped"})

    # A discoverable package that must never execute when a source override is set.
    trap = work / "package-trap"
    trap.mkdir()
    (trap / "OpenTLVConfig.cmake").write_text(
        'message(FATAL_ERROR "Package discovery must be bypassed by source override")\n',
        encoding="utf-8")
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
    for name in ("CMakeLists.txt", "CMakePresets.json", "cmake", "tests"):
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
