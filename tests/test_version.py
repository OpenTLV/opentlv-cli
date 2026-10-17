#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Marek Cingel
"""Exercise CLI Git versioning independently of Core and build-directory ancestry."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from baseline.run import differences
from check_cli_baseline import version_observation

MODULE = Path(__file__).resolve().parents[1] / "cmake/Version.cmake"


class Versions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cli-version-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / "cli"
        self.root.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.name", "Version test")
        self.git("config", "user.email", "version@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True,
                                       stderr=subprocess.STDOUT).strip()

    def commit(self):
        marker = self.root / "tracked"
        marker.write_text(marker.read_text() + "x" if marker.exists() else "x", encoding="utf-8")
        self.git("add", "tracked")
        self.git("commit", "--quiet", "-m", "Version fixture")

    def version(self, source=None, candidate=None, sha=None, failure=False):
        result = self.directory / "version.txt"
        script = self.directory / "version.cmake"
        script.write_text(f'include("{MODULE.as_posix()}")\n'
                          f'opentlv_cli_version("{(source or self.root).as_posix()}" value)\n'
                          f'file(WRITE "{result.as_posix()}" "${{value}}")\n', encoding="utf-8")
        command = ["cmake"]
        if candidate is not None:
            command += [f"-DOPENTLV_CLI_CANDIDATE_VERSION={candidate}", f"-DOPENTLV_CLI_CANDIDATE_SHA={sha}"]
        command += ["-P", str(script)]
        process = subprocess.run(command, capture_output=True, text=True)
        if failure:
            self.assertNotEqual(process.returncode, 0, process.stdout + process.stderr)
            return
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return result.read_text()

    def test_no_tags_is_development_version(self):
        self.assertRegex(self.version(), r"^0\.0\.0-dev\.1\+g[0-9a-f]{12}$")

    def test_exact_release_and_prerelease(self):
        for tag in ("v1.2.3", "v2.0.0-rc.1"):
            self.git("tag", tag)
            self.assertEqual(self.version(), tag[1:])
            self.git("tag", "-d", tag)

    def test_annotated_tag(self):
        self.git("tag", "-a", "v1.2.3", "-m", "Fixture tag")
        self.assertEqual(self.version(), "1.2.3")

    def test_multiple_version_tags_on_one_commit_are_ambiguous(self):
        self.git("tag", "v1.2.3")
        self.git("tag", "v1.2.4")
        self.version(failure=True)

    def test_commit_after_tag_and_dirty_worktree(self):
        self.git("tag", "v1.2.3")
        self.commit()
        version = self.version()
        self.assertRegex(version, r"^1\.2\.3-dev\.1\+g[0-9a-f]{12}$")
        (self.root / "tracked").write_text("changed", encoding="utf-8")
        self.assertEqual(self.version(), version + ".dirty")

    def test_prerelease_development(self):
        self.git("tag", "v1.2.3-rc.1")
        self.commit()
        self.assertRegex(self.version(), r"^1\.2\.3-rc\.1\.dev\.1\+g[0-9a-f]{12}$")

    def test_dirty_exact_tag_is_not_release(self):
        self.git("tag", "v1.2.3")
        (self.root / "untracked").touch()
        self.assertRegex(self.version(), r"^1\.2\.3\+g[0-9a-f]{12}\.dirty$")

    def test_core_style_tag_is_not_cli_tag(self):
        self.git("tag", "99.0.0")
        self.assertTrue(self.version().startswith("0.0.0-dev."))

    def test_export_does_not_inherit_enclosing_repo(self):
        self.git("tag", "v99.0.0")
        exported = self.root / "exported"
        exported.mkdir()
        self.assertEqual(self.version(source=exported), "0.0.0+unknown")

    def test_invalid_semver_tag_fails(self):
        for tag in ("v01.2.3", "v1.2.3-rc.01", "v1.2", "v1.2.3+metadata"):
            with self.subTest(tag=tag):
                self.git("tag", tag)
                self.version(failure=True)
                self.git("tag", "-d", tag)

    def test_candidate_version_needs_clean_exact_sha(self):
        sha = self.git("rev-parse", "HEAD")
        self.assertEqual(self.version(candidate="1.2.3", sha=sha), "1.2.3")
        self.assertEqual(self.git("tag", "--list"), "")
        self.version(candidate="1.2.3", sha="0" * 40, failure=True)
        self.version(candidate="1.02.3", sha=sha, failure=True)
        (self.root / "untracked").touch()
        self.version(candidate="1.2.3", sha=sha, failure=True)

    def test_shallow_checkout_cannot_claim_complete_version(self):
        self.commit()
        shallow = self.directory / "shallow"
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", self.root.as_uri(), str(shallow)], check=True)
        self.version(source=shallow, failure=True)

    def test_version_contract_preserves_other_observations(self):
        expected = version_observation("1.2.3")
        self.assertEqual(differences(expected, dict(expected, stdout="OpenTLV CLI 1.2.3\r\n")), [])
        for field, value in (("stdout", "otlv 0.7.1\n"), ("stderr", "oops"), ("exit", 1),
                             ("files", {"unexpected": "00"})):
            with self.subTest(field=field):
                self.assertEqual(differences(expected, dict(expected, **{field: value})), [field])


if __name__ == "__main__":
    unittest.main()
