import json
import unittest
from pathlib import Path

from tests.support import commit_file, load, make_repo, run_script
from tests.test_guard_gate import Repository

load("scripts/protected_paths.py")
gate_evidence = load("scripts/gate_evidence.py")
load("hooks/decision_log.py")
status = load("hooks/gate_status.py")


class ContextLineTest(unittest.TestCase):
    def test_nothing_to_say_when_no_steering_path_changed(self) -> None:
        self.assertIsNone(status.context_line(gate_evidence.State.NOT_NEEDED, "x"))

    def test_a_pass_is_reported_plainly(self) -> None:
        said = status.context_line(gate_evidence.State.PASS, "gate evidence pass: ok")
        self.assertIn("gate evidence pass", said)
        self.assertNotIn("Don't run", said)

    def test_anything_else_says_why_and_that_a_person_runs_the_gate(self) -> None:
        for state in (gate_evidence.State.MISSING, gate_evidence.State.STALE, gate_evidence.State.FAIL, gate_evidence.State.UNKNOWN):
            with self.subTest(state=state):
                said = status.context_line(state, f"gate evidence {state}: why")
                self.assertIn("a person decides", said)
                self.assertIn("Pushing is refused", said)


class SessionStartHookTest(unittest.TestCase):
    def run_hook(self, cwd: Path) -> dict[str, object] | None:
        payload = json.dumps({"session_id": "t", "hook_event_name": "SessionStart", "source": "startup", "cwd": str(cwd)})
        done = run_script("hooks/gate_status.py", stdin=payload, cwd=cwd, env={"CLAUDE_PROJECT_DIR": str(cwd)})
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout) if done.stdout.strip() else None

    def test_a_repository_without_a_gate_hears_nothing(self) -> None:
        handle, plain = make_repo()
        self.addCleanup(handle.cleanup)
        self.assertIsNone(self.run_hook(plain))

    def test_a_docs_only_branch_hears_nothing(self) -> None:
        world = Repository(self)
        commit_file(world.repo, "docs/guide.md", "words\n")
        self.assertIsNone(self.run_hook(world.repo))

    def test_a_steering_change_with_no_evidence_is_named(self) -> None:
        world = Repository(self)
        commit_file(world.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        said = self.run_hook(world.repo)["hookSpecificOutput"]
        self.assertEqual(said["hookEventName"], "SessionStart")
        self.assertIn("gate evidence missing", said["additionalContext"])
        self.assertIn("a person decides", said["additionalContext"])

    def test_passing_evidence_is_reported(self) -> None:
        world = Repository(self)
        commit_file(world.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        world.pass_the_gate()
        self.assertIn("gate evidence pass", self.run_hook(world.repo)["hookSpecificOutput"]["additionalContext"])

    def test_a_broken_payload_says_so_and_does_not_block(self) -> None:
        handle, plain = make_repo()
        self.addCleanup(handle.cleanup)
        done = run_script("hooks/gate_status.py", stdin="not json", cwd=plain, env={"CLAUDE_PROJECT_DIR": str(plain)})
        self.assertEqual(done.returncode, 0)
        self.assertIn("failed and said nothing", done.stderr)


if __name__ == "__main__":
    unittest.main()
