"""Static checks on the workflows that run with access the pull request doesn't control.

A workflow on `pull_request_target` runs from the base branch with the repository's
secrets. If it ever checked out or ran the pull request's code, anyone who can open a
pull request could reach those secrets, or loosen the checks that judge their change.
These tests read the workflow files as text, so they need nothing installed.
"""

import re
import unittest

from tests.support import ROOT

WORKFLOWS = ROOT / ".github" / "workflows"
BASE_BRANCH_WORKFLOWS = ("review.yml", "protected-paths.yml")


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text()


class BaseBranchWorkflowTest(unittest.TestCase):
    def test_each_runs_from_the_base_branch(self) -> None:
        for name in BASE_BRANCH_WORKFLOWS:
            with self.subTest(workflow=name):
                text = _text(name)
                self.assertRegex(text, r"(?m)^\s+pull_request_target:")
                self.assertNotRegex(text, r"(?m)^\s+pull_request:")

    def test_each_checks_out_only_the_base(self) -> None:
        for name in BASE_BRANCH_WORKFLOWS:
            with self.subTest(workflow=name):
                text = _text(name)
                # No ref at all: pull_request_target then checks out the base branch's
                # current tip. Any ref is either the pull request's code or a stale base.
                self.assertEqual(re.findall(r"(?m)^\s+ref:\s*(.+)$", text), [])
                self.assertNotIn("pull_request.base.sha", text)
                self.assertNotIn("github.event.pull_request.head", text)
                self.assertNotIn("github.head_ref", text)
                self.assertIn("persist-credentials: false", text)

    def test_each_holds_read_only_contents(self) -> None:
        for name in BASE_BRANCH_WORKFLOWS:
            with self.subTest(workflow=name):
                text = _text(name)
                self.assertIn("contents: read", text)
                self.assertNotRegex(text, r"(contents|issues|actions|id-token):\s*write")

    def test_only_the_review_can_write_and_only_pull_request_comments(self) -> None:
        self.assertNotRegex(_text("protected-paths.yml"), r":\s*write")
        self.assertEqual(re.findall(r"(?m)^\s+([\w-]+):\s*write", _text("review.yml")), ["pull-requests"])


class ReviewWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text("review.yml")

    def test_is_bounded(self) -> None:
        self.assertRegex(self.text, r"--max-turns \d+")
        self.assertRegex(self.text, r"timeout-minutes: \d+")

    def test_reads_the_rules_from_the_base_checkout(self) -> None:
        self.assertIn("--append-system-prompt-file REVIEW.md", self.text)
        self.assertTrue((ROOT / "REVIEW.md").exists())

    def test_can_only_post_inline_comments_beyond_the_skill_s_own_tools(self) -> None:
        allowed = re.findall(r'--allowedTools "([^"]+)"', self.text)
        self.assertEqual(allowed, ["mcp__github_inline_comment__create_inline_comment"])

    def test_records_cost_even_when_the_review_fails(self) -> None:
        self.assertRegex(self.text, r"(?s)if: always\(\).*review_cost\.py")


if __name__ == "__main__":
    unittest.main()
