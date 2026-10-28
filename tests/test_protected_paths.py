import unittest

from tests.support import commit_file, git, load, make_repo, run_script

protected = load("scripts/protected_paths.py")


class ViolationTest(unittest.TestCase):
    def test_plugin_and_evals_together_are_refused(self) -> None:
        problem = protected.violation(["skills/a/SKILL.md", "evals/case-1.json"])
        self.assertIsNotNone(problem)
        self.assertIn("evals/case-1.json", problem)
        self.assertIn("skills/a/SKILL.md", problem)

    def test_the_evals_definition_counts_as_the_suite(self) -> None:
        self.assertIsNotNone(protected.violation(["hooks/x.py", "spec/agentic-sdlc-plugin-evals.md"]))

    def test_either_alone_is_fine(self) -> None:
        self.assertIsNone(protected.violation(["skills/a/SKILL.md", "hooks/x.py"]))
        self.assertIsNone(protected.violation(["evals/case-1.json", "spec/a-evals.md"]))

    def test_artefacts_travel_with_either(self) -> None:
        self.assertIsNone(protected.violation(["evals/case-1.json", "intent/x.md", "plan/y.md", "README.md"]))
        self.assertIsNone(protected.violation(["skills/a/SKILL.md", "spec/a.md", "plan/y.md"]))


class IsSuiteTest(unittest.TestCase):
    def test_the_suite_is_evals_and_the_evals_definitions(self) -> None:
        for path in ("evals/cases/a/case.py", "evals/README.md", "spec/agentic-sdlc-plugin-evals.md"):
            self.assertTrue(protected.is_suite(path), path)
        for path in ("spec/agentic-sdlc-plugin.md", "scripts/eval", "skills/a/SKILL.md", "evals.md", "docs/evals/x.md"):
            self.assertFalse(protected.is_suite(path), path)


class ProtectedPathsScriptTest(unittest.TestCase):
    """The script as CI runs it, against a real branch."""

    def setUp(self) -> None:
        self.handle, self.repo = make_repo()
        commit_file(self.repo, "evals/case-1.json")
        git(self.repo, "checkout", "-q", "-b", "change")

    def tearDown(self) -> None:
        self.handle.cleanup()

    def run_check(self, *extra: str) -> int:
        return run_script("scripts/protected_paths.py", "--base", "main", *extra, cwd=self.repo).returncode

    def test_fails_a_branch_touching_skills_and_evals(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md")
        commit_file(self.repo, "evals/case-2.json")
        self.assertEqual(self.run_check(), 1)

    def test_a_rename_out_of_evals_still_counts(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md")
        (self.repo / "intent").mkdir()
        git(self.repo, "mv", "evals/case-1.json", "intent/case-1.json")
        git(self.repo, "commit", "-q", "-m", "move")
        self.assertEqual(self.run_check(), 1)

    def test_passes_a_branch_touching_skills_only(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md")
        self.assertEqual(self.run_check(), 0)

    def test_passes_a_branch_touching_evals_only(self) -> None:
        commit_file(self.repo, "evals/case-2.json")
        self.assertEqual(self.run_check(), 0)

    def test_compares_an_explicit_head_without_checking_it_out(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md")
        commit_file(self.repo, "evals/case-2.json")
        git(self.repo, "checkout", "-q", "main")
        self.assertEqual(self.run_check("--head", "change"), 1)

    def test_bad_arguments_print_usage(self) -> None:
        done = run_script("scripts/protected_paths.py", "--head", "x", cwd=self.repo)
        self.assertEqual(done.returncode, 2)
        self.assertIn("Usage", done.stderr)


if __name__ == "__main__":
    unittest.main()
