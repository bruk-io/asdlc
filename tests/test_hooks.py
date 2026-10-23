import json
import os
import shutil
import stat
import subprocess
import tempfile
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
            "lib/models/user_spec.rb",
            "Tests/Test_Upper.py",
            "pkg/conftest.py",
            "pkg/testdata/sample.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(guard.is_test_path(path))

    def test_ignores_source_files_and_specs_folders(self) -> None:
        for path in ("src/app.py", "testing.md", "contest/rules.py", "latest.ts", "spec/agentic-sdlc-plugin.md"):
            with self.subTest(path=path):
                self.assertFalse(guard.is_test_path(path))


class DecideFileTest(unittest.TestCase):
    def test_denies_only_existing_tests_on_fix_branches(self) -> None:
        cases = [
            ("fix/login", "tests/test_login.py", True, guard.Verdict.DENY),
            ("fix/login", "tests/test_new.py", False, guard.Verdict.ALLOW),
            ("fix/login", "src/login.py", True, guard.Verdict.ALLOW),
            ("fix/login", "tests/test_login.py", None, guard.Verdict.ERROR),
            ("main", "tests/test_login.py", True, guard.Verdict.ALLOW),
        ]
        for branch, path, exists, expected in cases:
            with self.subTest(branch=branch, path=path, exists=exists):
                self.assertIs(guard.decide_file(branch, path, exists).verdict, expected)

    def test_a_denial_says_why_and_what_to_do_instead(self) -> None:
        reason = guard.decide_file("fix/x", "tests/test_a.py", True).reason
        self.assertIn("proves", reason)
        self.assertIn("new test file", reason)

    def test_a_bug_task_is_a_fix_whatever_its_branch_is_called(self) -> None:
        cases = [
            ("task-3-lockout", "tests/test_login.py", True, "TASK-3", guard.Verdict.DENY),
            ("task-3-lockout", "tests/test_new.py", False, "TASK-3", guard.Verdict.ALLOW),
            ("task-3-lockout", "src/login.py", True, "TASK-3", guard.Verdict.ALLOW),
            ("task-3-lockout", "tests/test_login.py", None, "TASK-3", guard.Verdict.ERROR),
            ("task-3-lockout", "tests/test_login.py", True, None, guard.Verdict.ALLOW),
        ]
        for branch, path, exists, bug_task, expected in cases:
            with self.subTest(path=path, exists=exists, bug_task=bug_task):
                self.assertIs(guard.decide_file(branch, path, exists, bug_task).verdict, expected)
        reason = guard.decide_file("task-3-lockout", "tests/test_login.py", True, "TASK-3").reason
        self.assertIn("bug task TASK-3", reason)
        self.assertIn("new test file", reason)

    def test_the_marker_names_a_bug_task_only_when_its_type_is_bug(self) -> None:
        cases = [
            ('{"task": "TASK-3", "worker": "kyle.w1", "type": "bug"}', "TASK-3"),
            ('{"task": "TASK-3", "worker": "kyle.w1", "type": "task"}', None),
            ('{"task": "TASK-3", "worker": "kyle.w1"}', None),
            ("not json", None),
            (None, None),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(guard.bug_task_of(text), expected)

    def test_the_strongest_verdict_wins_across_repositories(self) -> None:
        allow, error, deny = (guard.Outcome(v, str(v)) for v in (guard.Verdict.ALLOW, guard.Verdict.ERROR, guard.Verdict.DENY))
        self.assertIs(guard.strongest((allow, error, deny)).verdict, guard.Verdict.DENY)
        self.assertIs(guard.strongest((allow, error)).verdict, guard.Verdict.ERROR)
        self.assertIs(guard.strongest((allow,)).verdict, guard.Verdict.ALLOW)
        self.assertIs(guard.strongest(()).verdict, guard.Verdict.ALLOW)


class AnchorsTest(unittest.TestCase):
    def test_folders_and_absolute_paths_a_command_names(self) -> None:
        self.assertEqual(
            guard.anchors("git -C /w/task-3 checkout -- tests/test_a.py && sed -i 's/a/b/' /v/tests/test_b.py"),
            (guard.Anchor("/w/task-3", True), guard.Anchor("/v/tests/test_b.py", False)),
        )
        self.assertEqual(
            guard.anchors("asdlc record-check TASK-3 --in /w/task-3 --as kyle.w1 -- rm tests/test_a.py"),
            (guard.Anchor("/w/task-3", True),),
        )
        self.assertEqual(guard.anchors("pytest tests/test_a.py"), ())
        self.assertEqual(
            guard.anchors("git --git-dir=/w/.git --work-tree=/w checkout main -- tests/test_a.py"),
            (guard.Anchor("/w/.git", False), guard.Anchor("/w", True)),
        )
        self.assertEqual(guard.anchors("git -C../w/task-3 status"), (guard.Anchor("../w/task-3", True),))
        self.assertEqual(guard.anchors("sed -i 's/a/b/' ~/src/w/tests/test_a.py"), (guard.Anchor("~/src/w/tests/test_a.py", False),))


class TestsWrittenByTest(unittest.TestCase):
    EXISTING = frozenset({"tests/test_a.py", "tests/test_b.py"})

    def written(self, command: str) -> tuple[str, ...]:
        return guard.tests_written_by(command, self.EXISTING, lambda word: word.removeprefix("./"))

    def test_catches_plain_writes_to_existing_tests(self) -> None:
        for command in (
            "sed -i 's/1/2/' tests/test_a.py",
            "echo x > tests/test_a.py",
            "echo x >> ./tests/test_a.py",
            "printf x | tee tests/test_a.py",
            "rm tests/test_a.py",
            "mv tests/test_a.py tests/test_c.py",
            "git checkout main -- tests/test_a.py",
            "git restore tests/test_a.py",
            "perl -pi -e 's/a/b/' tests/test_a.py",
            "git -C /w/task-3 checkout main -- tests/test_a.py",
            "sed -i 's/a|b/c/' tests/test_a.py",
            "cp tests/test_b.py tests/test_a.py",
            "install -m 644 tests/test_b.py tests/test_a.py",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.written(command), ("tests/test_a.py",))

    def test_allows_reading_running_and_new_files(self) -> None:
        for command in (
            "pytest tests/test_a.py",
            "cat tests/test_a.py",
            "pytest tests/test_a.py > out.txt 2>&1",
            "grep -n assert tests/test_b.py",
            "echo x > tests/test_new.py",
            "sed -i 's/1/2/' src/app.py",
            "cp tests/test_a.py tests/test_new.py",
            "uv pip install -e . && python -m pytest tests/test_a.py",
            "grep -C 3 assert tests/test_a.py",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.written(command), ())

    def test_decide_command(self) -> None:
        self.assertIs(guard.decide_command("fix/x", ("tests/test_a.py",)).verdict, guard.Verdict.DENY)
        self.assertIs(guard.decide_command("fix/x", ()).verdict, guard.Verdict.ALLOW)
        self.assertIs(guard.decide_command("fix/x", None).verdict, guard.Verdict.ERROR)
        self.assertIs(guard.decide_command("main", ("tests/test_a.py",)).verdict, guard.Verdict.ALLOW)
        self.assertIs(guard.decide_command("task-3-x", ("tests/test_a.py",), "TASK-3").verdict, guard.Verdict.DENY)
        self.assertIs(guard.decide_command("task-3-x", (), "TASK-3").verdict, guard.Verdict.ALLOW)


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

    def run_hook(self, tool: str, **tool_input: str) -> subprocess.CompletedProcess[str]:
        return run_script(
            "hooks/guard_test_edits.py",
            stdin=hook_payload(self.repo, tool, **tool_input),
            cwd=self.repo,
            env={"CLAUDE_PROJECT_DIR": str(self.repo)},
        )

    def log(self) -> list[dict[str, str]]:
        path = self.repo / ".asdlc" / "hooks.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_denies_an_edit_to_an_existing_test_and_logs_it(self) -> None:
        done = self.run_hook("Edit", file_path=str(self.repo / "tests/test_login.py"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual((self.log()[-1]["verdict"], self.log()[-1]["artefact"]), ("deny", "fix/login"))

    def test_denies_a_shell_write_to_an_existing_test(self) -> None:
        done = self.run_hook("Bash", command="sed -i 's/x/y/' tests/test_login.py")
        self.assertEqual(json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.log()[-1]["tool"], "Bash")

    def test_allows_running_the_tests(self) -> None:
        done = self.run_hook("Bash", command="python -m pytest tests/test_login.py")
        self.assertEqual((done.returncode, done.stdout), (0, ""))

    def test_allows_a_new_test(self) -> None:
        done = self.run_hook("Write", file_path=str(self.repo / "tests/test_new.py"))
        self.assertEqual((done.returncode, done.stdout), (0, ""))
        self.assertEqual(self.log()[-1]["verdict"], "allow")

    def test_allows_any_edit_off_a_fix_branch(self) -> None:
        git(self.repo, "checkout", "-q", "main")
        done = self.run_hook("Edit", file_path=str(self.repo / "tests/test_login.py"))
        self.assertEqual((done.returncode, done.stdout), (0, ""))
        self.assertEqual(self.log()[-1]["reason"], "not a fix branch")

    def test_finds_the_base_on_a_master_repository(self) -> None:
        git(self.repo, "branch", "-q", "-m", "main", "master")
        done = self.run_hook("Edit", file_path=str(self.repo / "tests/test_login.py"))
        self.assertEqual(json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_says_so_when_no_base_resolves(self) -> None:
        git(self.repo, "branch", "-q", "-m", "main", "unusual")
        done = self.run_hook("Edit", file_path=str(self.repo / "tests/test_login.py"))
        self.assertEqual(done.returncode, 0)
        self.assertIn("no base branch", json.loads(done.stdout)["systemMessage"])
        self.assertEqual(self.log()[-1]["verdict"], "error")

    def test_a_broken_payload_allows_says_so_and_logs_it(self) -> None:
        done = run_script(
            "hooks/guard_test_edits.py", stdin="not json", cwd=self.repo, env={"CLAUDE_PROJECT_DIR": str(self.repo)}
        )
        self.assertEqual(done.returncode, 0)
        self.assertIn("failed and allowed the change", done.stderr)
        self.assertIn("failed and allowed the change", json.loads(done.stdout)["systemMessage"])
        self.assertEqual(self.log()[-1]["verdict"], "error")


class BugTaskWorktreeTest(unittest.TestCase):
    """A board worker: its session stays in the tasks clone and writes its worktree by absolute path."""

    def setUp(self) -> None:
        self.handle, self.repo = make_repo()
        commit_file(self.repo, "tests/test_login.py")
        self.outside = tempfile.TemporaryDirectory()
        self.worktree = Path(self.outside.name) / "api.worktrees" / "task-3"
        git(self.repo, "worktree", "add", "-q", "-b", "task-3-lockout", str(self.worktree), "main")
        self.mark("bug")
        self.tasks_handle, self.tasks = make_repo()

    def tearDown(self) -> None:
        self.handle.cleanup()
        self.outside.cleanup()
        self.tasks_handle.cleanup()

    def mark(self, kind: str | None) -> None:
        marker = {"task": "TASK-3", "worker": "kyle.w1", "board": str(self.outside.name)} | ({"type": kind} if kind else {})
        (self.worktree / ".asdlc-task").write_text(json.dumps(marker))

    def run_hook(self, tool: str, **tool_input: str) -> subprocess.CompletedProcess[str]:
        return run_script(
            "hooks/guard_test_edits.py",
            stdin=hook_payload(self.tasks, tool, **tool_input),
            cwd=self.tasks,
            env={"CLAUDE_PROJECT_DIR": str(self.tasks)},
        )

    def verdict(self, done: subprocess.CompletedProcess[str]) -> str:
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] if done.stdout else "allow"

    def test_denies_an_edit_to_an_existing_test_by_absolute_path(self) -> None:
        done = self.run_hook("Edit", file_path=str(self.worktree / "tests/test_login.py"))
        self.assertEqual(self.verdict(done), "deny")
        self.assertIn("bug task TASK-3", json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"])

    def test_allows_a_new_test_file(self) -> None:
        self.assertEqual(self.verdict(self.run_hook("Write", file_path=str(self.worktree / "tests/test_lockout.py"))), "allow")

    def test_denies_shell_writes_through_absolute_paths_dash_c_and_in(self) -> None:
        for command in (
            f"sed -i 's/x/y/' {self.worktree}/tests/test_login.py",
            f"git -C {self.worktree} checkout main -- tests/test_login.py",
            f"asdlc record-check TASK-3 --in {self.worktree} --as kyle.w1 -- rm tests/test_login.py",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(self.run_hook("Bash", command=command)), "deny")

    def test_allows_running_the_tests(self) -> None:
        command = f"asdlc record-check TASK-3 --in {self.worktree} --as kyle.w1 -- python -m pytest tests/test_login.py"
        self.assertEqual(self.verdict(self.run_hook("Bash", command=command)), "allow")

    def test_denies_through_relative_folders_and_git_dir(self) -> None:
        relative = os.path.relpath(self.worktree, self.tasks)
        for command in (
            f"git -C {relative} checkout main -- tests/test_login.py",
            f"git --git-dir={self.worktree}/.git --work-tree={self.worktree} checkout main -- tests/test_login.py",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(self.run_hook("Bash", command=command)), "deny")

    def test_allows_starting_a_new_test_from_a_copy_and_other_harmless_lines(self) -> None:
        for command in (
            f"cp {self.worktree}/tests/test_login.py {self.worktree}/tests/test_lockout.py",
            f"grep -C 3 assert {self.worktree}/tests/test_login.py",
            "sed -i '/foo/d' /nonexistent/folder/notes.txt",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(self.run_hook("Bash", command=command)), "allow")

    def test_an_ordinary_task_may_change_its_tests(self) -> None:
        self.mark("task")
        self.assertEqual(self.verdict(self.run_hook("Edit", file_path=str(self.worktree / "tests/test_login.py"))), "allow")
        self.assertEqual(self.verdict(self.run_hook("Bash", command=f"sed -i 's/x/y/' {self.worktree}/tests/test_login.py")), "allow")

    def test_a_marker_from_before_types_were_recorded_allows(self) -> None:
        self.mark(None)
        self.assertEqual(self.verdict(self.run_hook("Edit", file_path=str(self.worktree / "tests/test_login.py"))), "allow")


class HookCommandTest(unittest.TestCase):
    """The shell command in hooks.json, which wraps uv."""

    def command(self) -> str:
        config = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        return config["hooks"]["PreToolUse"][0]["hooks"][0]["command"]

    def run_with_fake_uv(self, exit_code: int) -> subprocess.CompletedProcess[str]:
        bin_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bin_dir)
        fake = bin_dir / "uv"
        fake.write_text(f"#!/bin/sh\nexit {exit_code}\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = {**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        return subprocess.run(["sh", "-c", self.command()], input="{}", text=True, capture_output=True, env=env)

    def test_uv_failing_to_start_never_blocks(self) -> None:
        done = self.run_with_fake_uv(2)
        self.assertEqual(done.returncode, 1)
        self.assertIn("did not run", done.stderr)

    def test_the_guard_exit_code_passes_through(self) -> None:
        self.assertEqual(self.run_with_fake_uv(0).returncode, 0)

    def test_missing_uv_never_blocks(self) -> None:
        env = {**os.environ, "PATH": "/nonexistent", "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        done = subprocess.run(["/bin/sh", "-c", self.command()], input="{}", text=True, capture_output=True, env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("uv is not installed", done.stderr)


@unittest.skipUnless(shutil.which("uv"), "uv is not installed")
class WarmStartTest(unittest.TestCase):
    """The guard runs on every edit and command through uv, so its warm start is measured."""

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
