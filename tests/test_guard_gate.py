import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, commit_file, git, hook_payload, load, make_repo, run_script

load("scripts/protected_paths.py")
gate_evidence = load("scripts/gate_evidence.py")
load("hooks/decision_log.py")
load("hooks/guard_board.py")
load("hooks/guard_test_edits.py")
guard = load("hooks/guard_gate.py")


def decide(command: str, cwd: Path | None = None) -> object:
    return guard.decide_command(command, cwd)


class EvidencePathTest(unittest.TestCase):
    def test_only_the_two_evidence_folders_count(self) -> None:
        for path in (".eval-results/gate/a.json", ".eval-results/run-1/t.jsonl", ".asdlc/hooks.jsonl"):
            self.assertTrue(guard.is_evidence(path), path)
        for path in ("docs/.eval-results/a", "evals/cases/a/case.py", ".eval-results-notes.md", "asdlc/x"):
            self.assertFalse(guard.is_evidence(path), path)

    def test_a_shell_write_to_evidence_is_seen_and_a_read_is_not(self) -> None:
        def relative(word: str) -> str:
            return word

        for command in (
            "echo '{}' > .eval-results/gate/a.json",
            "cat x >> .asdlc/hooks.jsonl",
            "tee .eval-results/gate/a.json",
            "rm -rf .eval-results/gate",
            "cp forged.json .eval-results/gate/a.json",
            "sed -i s/fail/pass/ .eval-results/gate/a.json",
            "mv forged .asdlc/hooks.jsonl",
        ):
            with self.subTest(command=command):
                self.assertTrue(guard.shell_evidence_writes(command, relative), command)
        for command in ("cat .eval-results/gate/a.json", "ls .asdlc", "grep pass .eval-results/gate/a.json", "git status"):
            with self.subTest(command=command):
                self.assertEqual(guard.shell_evidence_writes(command, relative), ())


class BypassTest(unittest.TestCase):
    def test_no_verify_on_commit_or_push_is_refused_with_why(self) -> None:
        for subcommand, arguments in (("commit", ["--no-verify", "-m", "x"]), ("push", ["--no-verify", "origin", "work"]), ("commit", ["-nm", "x"]),
                                      ("commit", ["-n", "-m", "x"])):
            with self.subTest(subcommand=subcommand, arguments=arguments):
                outcome = guard.bypass_refusal(subcommand, arguments)
                self.assertIs(outcome.verdict, guard.Verdict.DENY)
                self.assertIn("git hooks", outcome.reason)

    def test_ordinary_commits_and_pushes_are_left_alone(self) -> None:
        for subcommand, arguments in (("commit", ["-m", "x"]), ("commit", ["-am", "x"]), ("commit", ["--amend", "--no-edit"]), ("push", ["origin", "work"]),
                                      ("push", ["-n", "origin"]), ("status", ["--no-verify"]), ("log", [])):
            with self.subTest(subcommand=subcommand, arguments=arguments):
                self.assertIsNone(guard.bypass_refusal(subcommand, arguments))

    def test_dry_run_is_not_a_push(self) -> None:
        self.assertTrue(guard.dry_run(["-n", "origin"]))
        self.assertTrue(guard.dry_run(["--dry-run"]))
        self.assertFalse(guard.dry_run(["origin", "work"]))


class R23Test(unittest.TestCase):
    def test_an_eval_edit_beside_a_plugin_change_is_refused_and_the_reverse(self) -> None:
        self.assertIs(guard.r23_refusal(["skills/a/SKILL.md"], "evals/cases/a/case.py").verdict, guard.Verdict.DENY)
        self.assertIs(guard.r23_refusal(["evals/cases/a/case.py"], "hooks/x.py").verdict, guard.Verdict.DENY)

    def test_either_side_alone_and_artefacts_beside_either_are_fine(self) -> None:
        self.assertIsNone(guard.r23_refusal(["skills/a/SKILL.md"], "hooks/x.py"))
        self.assertIsNone(guard.r23_refusal(["evals/a.py"], "evals/b.py"))
        self.assertIsNone(guard.r23_refusal(["plan/x.md", "README.md"], "evals/b.py"))
        self.assertIsNone(guard.r23_refusal([], "evals/b.py"))


class Repository:
    """A repository that has an eval gate (the runner and a suite folder), on a work branch off main."""

    def __init__(self, test: unittest.TestCase) -> None:
        handle, self.repo = make_repo()
        test.addCleanup(handle.cleanup)
        commit_file(self.repo, "scripts/eval", "#!/bin/sh\n")
        commit_file(self.repo, "evals/cases/c/case.toml", "x = 1\n")
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\n")
        commit_file(self.repo, "CLAUDE.md", "# rules\n")
        git(self.repo, "branch", "-M", "main")
        git(self.repo, "switch", "-q", "-c", "work")

    def pass_the_gate(self) -> None:
        steering, suite = gate_evidence.current(self.repo)
        transcript = self.repo / ".eval-results" / "run-1" / "t.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text("{}\n")
        report = {"schema": gate_evidence.SCHEMA, "created": "now", "steering": steering, "suite": suite, "verdict": "pass",
                  "transcripts": {"run-1/t.jsonl": hashlib.sha256(transcript.read_bytes()).hexdigest()}}
        path = gate_evidence.report_file(self.repo, gate_evidence.key(steering, suite))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report))


class HookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.world = Repository(self)
        self.repo = self.world.repo

    def run_hook(self, cwd: Path, tool: str, **tool_input: str) -> subprocess.CompletedProcess[str]:
        return run_script("hooks/guard_gate.py", stdin=hook_payload(cwd, tool, **tool_input), cwd=cwd, env={"CLAUDE_PROJECT_DIR": str(cwd)})

    def decision(self, done: subprocess.CompletedProcess[str]) -> str:
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] if done.stdout.startswith("{\"hookSpecificOutput") else "allow"

    def reason(self, done: subprocess.CompletedProcess[str]) -> str:
        return json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    def log(self) -> list[dict[str, str]]:
        return [json.loads(line) for line in (self.repo / ".asdlc" / "hooks.jsonl").read_text().splitlines()]

    def test_writing_evidence_with_the_file_tools_is_denied_and_logged(self) -> None:
        for tool, key, path in (("Write", "file_path", ".eval-results/gate/a.json"), ("Edit", "file_path", str(self.repo / ".asdlc" / "hooks.jsonl"))):
            with self.subTest(path=path):
                done = self.run_hook(self.repo, tool, **{key: path})
                self.assertEqual(self.decision(done), "deny")
                self.assertIn("scripts/eval", self.reason(done))
        entry = self.log()[-1]
        self.assertEqual((entry["hook"], entry["verdict"]), ("guard_gate", "deny"))

    def test_writing_evidence_from_the_shell_is_denied(self) -> None:
        done = self.run_hook(self.repo, "Bash", command="echo '{}' > .eval-results/gate/a.json")
        self.assertEqual(self.decision(done), "deny")
        self.assertEqual(self.decision(self.run_hook(self.repo, "Bash", command="cat .eval-results/gate/a.json")), "allow")

    def test_an_ordinary_edit_is_allowed(self) -> None:
        self.assertEqual(self.decision(self.run_hook(self.repo, "Edit", file_path="README.md")), "allow")
        self.assertEqual(self.decision(self.run_hook(self.repo, "Write", file_path="skills/a/SKILL.md")), "allow")

    def test_an_eval_edit_on_a_branch_that_already_changes_the_plugin_is_denied(self) -> None:
        commit_file(self.repo, "hooks/new.py", "x = 1\n")
        done = self.run_hook(self.repo, "Edit", file_path="evals/cases/c/case.toml")
        self.assertEqual(self.decision(done), "deny")
        self.assertIn("branch of its own", self.reason(done))

    def test_a_plugin_edit_on_a_branch_that_already_changes_the_suite_is_denied(self) -> None:
        commit_file(self.repo, "evals/cases/d/case.toml", "y = 1\n")
        self.assertEqual(self.decision(self.run_hook(self.repo, "Write", file_path="skills/a/SKILL.md")), "deny")
        self.assertEqual(self.decision(self.run_hook(self.repo, "Write", file_path="plan/x.md")), "allow")

    def test_a_push_with_steering_changes_and_no_evidence_is_denied_with_the_command(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        done = self.run_hook(self.repo, "Bash", command="git push origin work")
        self.assertEqual(self.decision(done), "deny")
        reason = self.reason(done)
        self.assertIn("scripts/eval gate", reason)
        self.assertIn("spends tokens", reason)
        self.assertIn("ask the person", reason)

    def test_a_push_is_allowed_with_passing_evidence_for_what_is_on_disk(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        self.world.pass_the_gate()
        self.assertEqual(self.decision(self.run_hook(self.repo, "Bash", command="git push origin work")), "allow")

    def test_evidence_for_older_content_does_not_cover_a_later_edit(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        self.world.pass_the_gate()
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnewer\n")
        self.assertEqual(self.decision(self.run_hook(self.repo, "Bash", command="git push origin work")), "deny")

    def test_a_push_that_changes_no_steering_path_needs_no_evidence(self) -> None:
        commit_file(self.repo, "docs/guide.md", "words\n")
        self.assertEqual(self.decision(self.run_hook(self.repo, "Bash", command="git push origin work")), "allow")

    def test_a_dry_run_is_not_judged(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        self.assertEqual(self.decision(self.run_hook(self.repo, "Bash", command="git push --dry-run origin work")), "allow")

    def test_the_push_is_found_through_cd_git_c_and_a_shell(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        elsewhere = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, elsewhere)
        for command in (f"cd {self.repo} && git push origin work", f"git -C {self.repo} push origin work", f"bash -c 'cd {self.repo} && git push'",
                        f"echo hi; git -C {self.repo} push --force-with-lease origin work"):
            with self.subTest(command=command):
                self.assertEqual(self.decision(self.run_hook(elsewhere, "Bash", command=command)), "deny")

    def test_no_verify_is_denied_with_or_without_evidence(self) -> None:
        self.world.pass_the_gate()
        for command in ("git commit --no-verify -m x", "git push --no-verify origin work", "git commit -nm x"):
            with self.subTest(command=command):
                done = self.run_hook(self.repo, "Bash", command=command)
                self.assertEqual(self.decision(done), "deny")
                self.assertIn("git hooks", self.reason(done))

    def test_no_base_allows_and_says_so_rather_than_passing_silently(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        git(self.repo, "branch", "-m", "work", "trunk")
        git(self.repo, "branch", "-D", "main")
        done = self.run_hook(self.repo, "Bash", command="git push origin trunk")
        self.assertEqual(self.decision(done), "allow")
        self.assertIn("no base", json.loads(done.stdout)["systemMessage"])
        self.assertEqual(self.log()[-1]["verdict"], "error")

    def test_a_repository_without_a_gate_is_left_entirely_alone(self) -> None:
        handle, plain = make_repo()
        self.addCleanup(handle.cleanup)
        commit_file(plain, "skills/a/SKILL.md", "x\n")
        for tool, tool_input in (("Bash", {"command": "git push --no-verify origin main"}), ("Bash", {"command": "echo x > .eval-results/a"}),
                                 ("Write", {"file_path": ".eval-results/gate/a.json"}), ("Write", {"file_path": "evals/x.py"})):
            with self.subTest(tool_input=tool_input):
                self.assertEqual(self.decision(self.run_hook(plain, tool, **tool_input)), "allow")

    def test_broken_input_allows_and_logs_the_failure(self) -> None:
        done = run_script("hooks/guard_gate.py", stdin="not json", cwd=self.repo, env={"CLAUDE_PROJECT_DIR": str(self.repo)})
        self.assertEqual(done.returncode, 0)
        self.assertIn("failed and allowed the change", done.stderr)

    def test_the_guard_never_asks(self) -> None:
        text = (ROOT / "hooks" / "guard_gate.py").read_text()
        self.assertNotRegex(text, r'"permissionDecision":\s*"ask"')
        self.assertNotIn("Outcome(Verdict.ASK", text)


class HookCommandTest(unittest.TestCase):
    """The gate guard's command in hooks.json, which wraps uv like the other guards'."""

    def command(self) -> str:
        config = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        group = config["hooks"]["PreToolUse"][0]
        self.assertEqual(group["matcher"], "Edit|Write|NotebookEdit|Bash")
        return next(hook["command"] for hook in group["hooks"] if "guard_gate.py" in hook["command"])

    def run_with_fake_uv(self, exit_code: int) -> subprocess.CompletedProcess[str]:
        bin_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bin_dir)
        fake = bin_dir / "uv"
        fake.write_text(f"#!/bin/sh\nexit {exit_code}\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = {**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        return subprocess.run(["sh", "-c", self.command()], input="{}", text=True, capture_output=True, env=env)

    def test_uv_failing_to_start_never_blocks_and_says_so(self) -> None:
        done = self.run_with_fake_uv(2)
        self.assertEqual(done.returncode, 1)
        self.assertIn("gate guard", done.stderr)

    def test_the_guard_exit_code_passes_through(self) -> None:
        self.assertEqual(self.run_with_fake_uv(0).returncode, 0)

    def test_missing_uv_never_blocks(self) -> None:
        env = {**os.environ, "PATH": "/nonexistent", "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        done = subprocess.run(["/bin/sh", "-c", self.command()], input="{}", text=True, capture_output=True, env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("uv is not installed, so the gate guard did not run", done.stderr)


if __name__ == "__main__":
    unittest.main()
