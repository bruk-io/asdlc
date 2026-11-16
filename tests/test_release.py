import json
import tempfile
import unittest
from pathlib import Path

from tests.support import run_script, load

release = load("scripts/release.py")

MANIFEST = '{\n  "name": "asdlc",\n  "version": "0.1.0",\n  "description": "The version is 0.1.0 here too"\n}\n'
CHANGELOG = "# Changelog\n\n## Unreleased\n\n### A change\n\n- What it did.\n\n## 0.1.0 - 2026-10-22\n\n- The first release.\n"


class BumpTest(unittest.TestCase):
    def test_the_version_is_set_and_the_entries_are_filed_under_it(self) -> None:
        manifest, changelog = release.bump(MANIFEST, CHANGELOG, "0.2.0", "2026-11-15")
        self.assertEqual(json.loads(manifest)["version"], "0.2.0")
        self.assertEqual(manifest, MANIFEST.replace('"version": "0.1.0"', '"version": "0.2.0"'), "nothing else in the manifest changes")
        self.assertEqual(changelog, "# Changelog\n\n## Unreleased\n\n## 0.2.0 - 2026-11-15\n\n### A change\n\n- What it did.\n\n## 0.1.0 - 2026-10-22\n\n- The first release.\n")

    def test_releasing_twice_in_a_row_is_refused_as_empty(self) -> None:
        manifest, changelog = release.bump(MANIFEST, CHANGELOG, "0.2.0", "2026-11-15")
        with self.assertRaisesRegex(release.ReleaseError, "nothing is under '## Unreleased'"):
            release.bump(manifest, changelog, "0.3.0", "2026-11-16")

    def test_a_version_that_is_not_newer_is_refused(self) -> None:
        for version in ("0.1.0", "0.0.9", "0.0.10"):
            with self.subTest(version=version), self.assertRaisesRegex(release.ReleaseError, f"{version} is not newer than 0.1.0"):
                release.bump(MANIFEST, CHANGELOG, version, "2026-11-15")

    def test_versions_compare_as_numbers(self) -> None:
        manifest, _ = release.bump(MANIFEST.replace("0.1.0", "0.9.0"), CHANGELOG, "0.10.0", "2026-11-15")
        self.assertEqual(json.loads(manifest)["version"], "0.10.0")

    def test_what_is_not_a_version_is_refused(self) -> None:
        for version in ("0.2", "v0.2.0", "0.2.0-beta", "", "latest"):
            with self.subTest(version=version), self.assertRaisesRegex(release.ReleaseError, "is not a version"):
                release.bump(MANIFEST, CHANGELOG, version, "2026-11-15")

    def test_a_manifest_or_changelog_of_the_wrong_shape_is_refused(self) -> None:
        with self.assertRaisesRegex(release.ReleaseError, '0 "version" fields'):
            release.bump('{"name": "asdlc"}', CHANGELOG, "0.2.0", "2026-11-15")
        with self.assertRaisesRegex(release.ReleaseError, "exactly one '## Unreleased'"):
            release.bump(MANIFEST, "# Changelog\n\n## 0.1.0 - 2026-10-22\n", "0.2.0", "2026-11-15")


class ReleaseCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.root = Path(handle.name)
        (self.root / ".claude-plugin").mkdir()
        (self.root / ".claude-plugin" / "plugin.json").write_text(MANIFEST)
        (self.root / "CHANGELOG.md").write_text(CHANGELOG)

    def test_it_writes_both_files_and_says_what_is_left_to_the_person(self) -> None:
        done = run_script("scripts/release.py", "0.2.0", "--date", "2026-11-15", "--root", str(self.root))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("git tag v0.2.0", done.stdout)
        self.assertEqual(json.loads((self.root / ".claude-plugin" / "plugin.json").read_text())["version"], "0.2.0")
        self.assertIn("## 0.2.0 - 2026-11-15\n", (self.root / "CHANGELOG.md").read_text())

    def test_a_refusal_writes_nothing(self) -> None:
        done = run_script("scripts/release.py", "0.1.0", "--root", str(self.root))
        self.assertEqual((done.returncode, done.stdout), (1, ""))
        self.assertIn("release: 0.1.0 is not newer than 0.1.0", done.stderr)
        self.assertEqual(((self.root / ".claude-plugin" / "plugin.json").read_text(), (self.root / "CHANGELOG.md").read_text()), (MANIFEST, CHANGELOG))


if __name__ == "__main__":
    unittest.main()
