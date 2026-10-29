import os
import re
import shutil
import subprocess
import unittest

from tests.support import ROOT

RECIPES = {"setup", "check", "test", "artefacts", "conformance", "validate", "audit", "doctor", "try", "eval"}
TEXT = (ROOT / "justfile").read_text()


def recipe_names() -> set[str]:
    """The names of the recipes: a line at column 0 that ends in a colon after its name and parameters, not a setting or comment."""
    names = set()
    for line in TEXT.splitlines():
        if (found := re.match(r"^([a-z][a-z0-9_-]*)(?: [^:=]*)?:\s*$", line)):
            names.add(found.group(1))
    return names - {"default"}


class JustfileTest(unittest.TestCase):
    def test_the_recipes_are_exactly_the_standard_entrypoints(self) -> None:
        self.assertEqual(recipe_names(), RECIPES)

    def test_every_script_a_recipe_calls_exists_and_runs(self) -> None:
        paths = {a or b for a, b in re.findall(r"\./(scripts/[\w.-]+)|uv run --script (scripts/[\w.-]+)", TEXT)}
        self.assertTrue(paths)
        for path in sorted(paths):
            with self.subTest(script=path):
                self.assertTrue((ROOT / path).is_file(), path)
                if "." not in path.rsplit("/", 1)[-1]:  # a script without a suffix is run directly
                    self.assertTrue(os.access(ROOT / path, os.X_OK), f"{path} is not executable")

    def test_no_recipe_spends_tokens_on_its_own(self) -> None:
        """`eval` passes arguments through; nothing calls `run`, `gate` or `calibrate` itself."""
        self.assertFalse(re.search(r"scripts/eval\s+(run|gate|calibrate)\b", TEXT))

    @unittest.skipUnless(shutil.which("just"), "just is not installed")
    def test_just_reads_the_file_and_lists_every_recipe(self) -> None:
        listed = subprocess.run(["just", "--justfile", str(ROOT / "justfile"), "--summary"], capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(set(listed), RECIPES)

    @unittest.skipUnless(shutil.which("just"), "just is not installed")
    def test_a_dry_run_of_check_names_the_script(self) -> None:
        done = subprocess.run(["just", "--justfile", str(ROOT / "justfile"), "--dry-run", "check"], capture_output=True, text=True, check=True)
        self.assertIn("./scripts/check", done.stderr + done.stdout)


if __name__ == "__main__":
    unittest.main()
