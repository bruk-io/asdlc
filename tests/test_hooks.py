import json
import shutil
import subprocess
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tests.support import ROOT, commit_file, git, hook_payload, load, make_repo, run_script

decision_log = load("hooks/decision_log.py")
guard = load("hooks/guard_test_edits.py")


class IsTestPathTest(unittest.TestCase):
    def test_recognises_common_test_layouts(self) -> None:
        for path in (
            "tests/test_a.py",
            "pkg/test_b.py",
            "src/a_test.go",
            "web/a.test.ts",
            "web/__tests__/a.tsx",
            "app/src/test/java/FooTest.java",
            "spec/models/user_spec.rb",
        ):
            with self.subTest(path=path):
                self.assertTrue(guard.is_test_path(path))

    def test_ignores_source_files(self) -> None:
        for path in ("src/app.py", "testing.md", "contest/rules.py", "latest.ts"):
            with self.subTest(path=path):
                self.assertFalse(guard.is_test_path(path))


class DecideTest(unittest.TestCase):
    def test_denies_only_existing_tests_on_fix_branches(self) -> None:
        cases = [
            ("fix/login", "tests/test_login.py", True, guard.Verdict.DENY),
            ("fix/login", "tests/test_new.py", False, guard.Verdict.ALLOW),
            ("fix/login", "src/login.py", True, guard.Verdict.ALLOW),
            ("main", "tests/test_login.py", True, guard.Verdict.ALLOW),
            ("feature/x", "tests/test_login.py", True, guard.Verdict.ALLOW),
        ]
        for branch, path, exists, expected in cases:
            with self.subTest(branch=branch, path=path, exists=exists):
                self.assertIs(guard.decide(branch, path, exists).verdict, expected)

    def test_a_denial_says_why_and_what_to_do_instead(self) -> None:
        reason = guard.decide("fix/x", "tests/test_a.py", True).reason
        self.assertIn("proves", reason)
        self.assertIn("new test file", reason)


class DecisionLogTest(unittest.TestCase):
    def test_a_decision_is_one_json_line_in_utc(self) -> None:
        entry = decision_log.decision(
            datetime(2026, 10, 20, 18, 0, tzinfo=UTC), "h", "Edit", decision_log.Verdict.DENY, "why", "fix/x"
        )
        self.assertEqual(
            json.loads(entry.to_line()),
            {"artefact": "fix/x", "hook": "h", "reason": "why", "time": "2026-10-20T18:00:00+00:00", "tool": "Edit", "verdict": "deny"},
        )


class GuardHookTest(unittest.TestCase):
    """The hook as Claude Code runs it: a subprocess reading the payload on stdin."""

    def setUp(self) -> None:
        self.handle, self.repo = make_repo()
        commit_file(self.repo, "tests/test_login.py")
        git(self.repo, "checkout", "-q", "-b", "fix/login")

    def tearDown(self) -> None:
        self.handle.cleanup()

    def run_hook(self, file_path: str) -> subprocess.CompletedProcess[str]:
        return run_script(
            "hooks/guard_test_edits.py",
            stdin=hook_payload(self.repo, "Edit", file_path=str(self.repo / file_path)),
            cwd=self.repo,
            env={"CLAUDE_PROJECT_DIR": str(self.repo)},
        )

    def log(self) -> list[dict[str, str]]:
        path = self.repo / ".asdlc" / "hooks.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_denies_an_existing_test_and_logs_it(self) -> None:
        done = self.run_hook("tests/test_login.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        output = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertEqual(self.log()[-1]["verdict"], "deny")
        self.assertEqual(self.log()[-1]["artefact"], "fix/login")

    def test_allows_a_new_test_and_logs_it(self) -> None:
        done = self.run_hook("tests/test_new.py")
        self.assertEqual((done.returncode, done.stdout), (0, ""))
        self.assertEqual(self.log()[-1]["verdict"], "allow")

    def test_allows_any_edit_off_a_fix_branch(self) -> None:
        git(self.repo, "checkout", "-q", "main")
        done = self.run_hook("tests/test_login.py")
        self.assertEqual((done.returncode, done.stdout), (0, ""))
        self.assertEqual(self.log()[-1]["reason"], "not a fix branch")

    def test_a_broken_payload_allows_and_says_so(self) -> None:
        done = run_script("hooks/guard_test_edits.py", stdin="not json", cwd=self.repo)
        self.assertEqual((done.returncode, done.stdout), (0, ""))
        self.assertIn("failed and allowed the edit", done.stderr)


@unittest.skipUnless(shutil.which("uv"), "uv is not installed")
class WarmStartTest(unittest.TestCase):
    """The guard runs on every edit through uv, so its warm start is measured (plan risk)."""

    def test_warm_start_through_uv(self) -> None:
        handle, repo = make_repo()
        self.addCleanup(handle.cleanup)
        command = ["uv", "run", "--quiet", "--script", str(ROOT / "hooks" / "guard_test_edits.py")]
        payload = hook_payload(repo, "Edit", file_path=str(repo / "a.py"))
        subprocess.run(command, input=payload, text=True, capture_output=True, cwd=repo)  # warm the cache
        started = time.perf_counter()
        done = subprocess.run(command, input=payload, text=True, capture_output=True, cwd=repo)
        elapsed = time.perf_counter() - started
        print(f"\n  warm hook start through uv: {elapsed:.2f}s", flush=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
