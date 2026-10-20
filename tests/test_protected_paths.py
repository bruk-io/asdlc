import unittest

from tests.support import commit_file, git, load, make_repo, run_script

protected = load("scripts/protected_paths.py")


class ViolationTest(unittest.TestCase):
    def test_plugin_and_evals_together_are_refused(self) -> None:
        problem = protected.violation(["skills/a/SKILL.md", "evals/case-1.json"])
        self.assertIsNotNone(problem)
        self.assertIn("evals/case-1.json", problem)
        self.assertIn("skills/a/SKILL.md", problem)

    def test_either_alone_is_fine(self) -> None:
        self.assertIsNone(protected.violation(["skills/a/SKILL.md", "hooks/x.py"]))
        self.assertIsNone(protected.violation(["evals/case-1.json"]))

    def test_artefacts_travel_with_evals(self) -> None:
        self.assertIsNone(protected.violation(["evals/case-1.json", "intent/x.md", "plan/y.md", "README.md"]))


class ProtectedPathsScriptTest(unittest.TestCase):
    """The script as CI runs it, against a real branch."""

    def setUp(self) -> None:
        self.handle, self.repo = make_repo()
        git(self.repo, "checkout", "-q", "-b", "change")

    def tearDown(self) -> None:
        self.handle.cleanup()

    def run_check(self) -> int:
        return run_script("scripts/protected_paths.py", "--base", "main", cwd=self.repo).returncode

    def test_fails_a_branch_touching_skills_and_evals(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md")
        commit_file(self.repo, "evals/case-1.json")
        self.assertEqual(self.run_check(), 1)

    def test_passes_a_branch_touching_skills_only(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md")
        self.assertEqual(self.run_check(), 0)

    def test_passes_a_branch_touching_evals_only(self) -> None:
        commit_file(self.repo, "evals/case-1.json")
        self.assertEqual(self.run_check(), 0)


if __name__ == "__main__":
    unittest.main()
