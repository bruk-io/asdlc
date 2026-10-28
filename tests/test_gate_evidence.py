import hashlib
import json
import unittest
from pathlib import Path

from tests.support import commit_file, git, load, make_repo, run_script

load("scripts/protected_paths.py")  # scripts/gate_evidence.py imports it from beside itself
gate = load("scripts/gate_evidence.py")

STEERING = {"CLAUDE.md": "a", "skills": "b", "hooks": "c", "agents": "d", "commands": "e"}


def report(**fields: object) -> dict[str, object]:
    return {"schema": gate.SCHEMA, "created": "2026-10-28T10:00:00+00:00", "steering": dict(STEERING), "suite": "s",
            "verdict": "pass", "transcripts": {"run-1/t.jsonl": "t1"}} | fields


def verify(found: dict[str, object] | None, **overrides: object) -> object:
    arguments = {"steering": dict(STEERING), "suite": "s", "transcripts": {"run-1/t.jsonl": "t1"}} | overrides
    return gate.verify(found, **arguments)


class WhatNeedsEvidenceTest(unittest.TestCase):
    def test_steering_is_claude_md_and_the_four_folders(self) -> None:
        for path in ("CLAUDE.md", "skills/a/SKILL.md", "hooks/guard.py", "agents/worker.md", "commands/plan.md"):
            self.assertTrue(gate.is_steering(path), path)

    def test_nothing_else_is_steering(self) -> None:
        for path in ("README.md", "docs/guide.md", "plan/x.md", "evals/cases/a/case.py", "scripts/eval", "skills-notes.md", "hooks.md"):
            self.assertFalse(gate.is_steering(path), path)

    def test_a_change_needs_evidence_only_when_it_touches_steering(self) -> None:
        self.assertTrue(gate.needs_evidence(["README.md", "skills/a/SKILL.md"]))
        self.assertFalse(gate.needs_evidence(["README.md", "docs/guide.md"]))
        self.assertFalse(gate.needs_evidence([]))

    def test_the_digest_does_not_depend_on_order(self) -> None:
        self.assertEqual(gate.digest([("a", "1"), ("b", "2")]), gate.digest([("b", "2"), ("a", "1")]))
        self.assertNotEqual(gate.digest([("a", "1")]), gate.digest([("a", "2")]))
        self.assertNotEqual(gate.digest([("a", "12")]), gate.digest([("a1", "2")]))


class VerifyTest(unittest.TestCase):
    def test_a_matching_passing_report_passes(self) -> None:
        verdict = verify(report())
        self.assertEqual(verdict.state, gate.State.PASS)
        self.assertTrue(verdict.holds)

    def test_no_report_is_missing_and_names_the_command_and_the_cost(self) -> None:
        verdict = verify(None)
        self.assertEqual(verdict.state, gate.State.MISSING)
        self.assertFalse(verdict.holds)
        self.assertIn("scripts/eval gate", verdict.reason)
        self.assertIn("spends tokens", verdict.reason)

    def test_a_changed_steering_path_is_stale_and_names_it(self) -> None:
        verdict = verify(report(), steering=STEERING | {"skills": "changed"})
        self.assertEqual(verdict.state, gate.State.STALE)
        self.assertIn("skills", verdict.reason)
        self.assertNotIn("hooks", verdict.reason)

    def test_a_changed_suite_is_stale(self) -> None:
        verdict = verify(report(), suite="other")
        self.assertEqual(verdict.state, gate.State.STALE)
        self.assertIn("eval suite", verdict.reason)

    def test_another_schema_is_stale(self) -> None:
        self.assertEqual(verify(report(schema=0)).state, gate.State.STALE)

    def test_a_report_with_no_transcripts_listed_is_stale(self) -> None:
        self.assertEqual(verify(report(transcripts=None)).state, gate.State.STALE)

    def test_a_missing_transcript_fails_the_report(self) -> None:
        verdict = verify(report(), transcripts={"run-1/t.jsonl": None})
        self.assertEqual(verdict.state, gate.State.FAIL)
        self.assertIn("is gone", verdict.reason)

    def test_an_edited_transcript_fails_the_report(self) -> None:
        verdict = verify(report(), transcripts={"run-1/t.jsonl": "other"})
        self.assertEqual(verdict.state, gate.State.FAIL)
        self.assertIn("was edited", verdict.reason)

    def test_a_failing_run_fails_with_its_summary(self) -> None:
        verdict = verify(report(verdict="fail", summary="small-request-no-intent: 1 of 3 passed"))
        self.assertEqual(verdict.state, gate.State.FAIL)
        self.assertIn("small-request-no-intent", verdict.reason)

    def test_not_needed_holds_without_a_report(self) -> None:
        self.assertTrue(gate.Verdict(gate.State.NOT_NEEDED, "x").holds)


def row(suite: str, trials: int, passed: int, **failing: int) -> dict[str, object]:
    return {"suite": suite, "trials": trials, "passed": passed, "failing_checks": failing}


class SelectTest(unittest.TestCase):
    SUITES = {"a": "regression", "b": "capability", "c": "regression"}

    def test_a_change_with_no_steering_path_runs_nothing(self) -> None:
        self.assertIsNone(gate.select_cases(["README.md", "docs/guide.md"], self.SUITES, False))

    def test_a_steering_change_runs_the_regression_cases(self) -> None:
        self.assertEqual(gate.select_cases(["skills/a/SKILL.md"], self.SUITES, False), ("a", "c"))

    def test_everything_runs_every_case_even_for_a_docs_only_change(self) -> None:
        self.assertEqual(gate.select_cases(["README.md"], self.SUITES, True), ("a", "b", "c"))


class JudgeTest(unittest.TestCase):
    def test_every_trial_of_every_regression_case_must_pass(self) -> None:
        verdict = gate.judge(["a", "c"], {"a": row("regression", 3, 3), "c": row("regression", 3, 3)}, None)
        self.assertTrue(verdict.passed)
        self.assertIn("2 regression cases, every trial passed", verdict.summary)

    def test_one_failing_trial_fails_the_gate_and_names_the_check(self) -> None:
        verdict = gate.judge(["a", "c"], {"a": row("regression", 3, 2, no_force_push=1), "c": row("regression", 3, 3)}, None)
        self.assertFalse(verdict.passed)
        self.assertIn("a: 2 of 3 trials passed (failing: no_force_push x1)", verdict.failures)

    def test_a_selected_case_that_produced_no_trials_fails_never_passes_silently(self) -> None:
        verdict = gate.judge(["a", "c"], {"a": row("regression", 3, 3)}, None)
        self.assertFalse(verdict.passed)
        self.assertIn("c: selected but produced no trials", verdict.failures)

    def test_nothing_run_is_not_a_pass_for_the_cases_asked_for(self) -> None:
        self.assertFalse(gate.judge(["a"], {}, None).passed)

    def test_capability_cases_are_reported_only_without_a_baseline(self) -> None:
        verdict = gate.judge(["b"], {"b": row("capability", 3, 0)}, None)
        self.assertTrue(verdict.passed)
        self.assertIn("reported only", verdict.summary)

    def test_a_capability_drop_beyond_noise_fails(self) -> None:
        was = {name: row("capability", 3, 3) for name in "bcde"}
        now = {name: row("capability", 3, 0) for name in "bcde"}
        verdict = gate.judge(list(now), now, was)
        self.assertFalse(verdict.passed)
        self.assertIn("fell from 1.00 to 0.00", verdict.summary)

    def test_a_capability_wobble_inside_noise_passes(self) -> None:
        was = {"b": row("capability", 3, 2), "c": row("capability", 3, 1), "d": row("capability", 3, 3)}
        now = {"b": row("capability", 3, 1), "c": row("capability", 3, 2), "d": row("capability", 3, 3)}
        verdict = gate.judge(list(now), now, was)
        self.assertTrue(verdict.passed, verdict.summary)
        self.assertIn("no worse than the baseline", verdict.summary)

    def test_a_new_capability_case_is_reported_only(self) -> None:
        was = {"b": row("capability", 3, 2)}
        now = {"b": row("capability", 3, 2), "z": row("capability", 3, 0)}
        verdict = gate.judge(["b", "z"], now, was)
        self.assertTrue(verdict.passed)
        self.assertIn("z not in the baseline", verdict.summary)


class ReportTest(unittest.TestCase):
    def test_a_built_report_verifies_against_what_it_digested(self) -> None:
        verdict = gate.judge(["a"], {"a": row("regression", 3, 3)}, None)
        built = gate.build_report(created="t", steering=STEERING, suite="s", judgement=verdict, summary={"a": row("regression", 3, 3)},
                                  transcripts={"run-1/t.jsonl": "t1"}, meta={"model": "sonnet"}, base="abc", scope="regression")
        self.assertEqual(built["verdict"], "pass")
        self.assertEqual(built["cases"], {"a": {"suite": "regression", "trials": 3, "passed": 3}})
        self.assertEqual(verify(built).state, gate.State.PASS)

    def test_a_failing_report_verifies_as_fail_with_the_reason(self) -> None:
        verdict = gate.judge(["a"], {"a": row("regression", 3, 1, x=2)}, None)
        built = gate.build_report(created="t", steering=STEERING, suite="s", judgement=verdict, summary={"a": row("regression", 3, 1)},
                                  transcripts={"run-1/t.jsonl": "t1"}, meta={}, base="abc", scope="regression")
        found = verify(built)
        self.assertEqual(found.state, gate.State.FAIL)
        self.assertIn("1 of 3 trials passed", found.reason)


class OnDiskTest(unittest.TestCase):
    """The shell: a real repository, with the report written where `eval gate` writes it."""

    def setUp(self) -> None:
        handle, self.repo = make_repo()
        self.addCleanup(handle.cleanup)
        commit_file(self.repo, "CLAUDE.md", "# rules\n")
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\n")
        commit_file(self.repo, "evals/cases/c/case.toml", "x = 1\n")
        commit_file(self.repo, "README.md", "hello\n")
        git(self.repo, "branch", "-M", "main")
        git(self.repo, "switch", "-q", "-c", "work")

    def write_passing_report(self) -> Path:
        steering, suite = gate.current(self.repo)
        transcript = self.repo / ".eval-results" / "run-1" / "t.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("{}\n")
        found = report(steering=steering, suite=suite, transcripts={"run-1/t.jsonl": hashlib.sha256(transcript.read_bytes()).hexdigest()})
        path = gate.report_file(self.repo, gate.key(steering, suite))
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(found))
        return path

    def test_a_change_that_touches_no_steering_path_needs_nothing(self) -> None:
        commit_file(self.repo, "docs/guide.md", "words\n")
        verdict = gate.check_change(self.repo, "main")
        self.assertEqual(verdict.state, gate.State.NOT_NEEDED)

    def test_a_steering_change_with_no_report_is_missing(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        verdict = gate.check_change(self.repo, "main")
        self.assertEqual(verdict.state, gate.State.MISSING)

    def test_a_passing_report_for_the_content_on_disk_passes(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        self.write_passing_report()
        self.assertEqual(gate.check_change(self.repo, "main").state, gate.State.PASS)

    def test_an_uncommitted_edit_after_the_run_means_no_report_for_it(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        self.write_passing_report()
        (self.repo / "skills" / "a" / "SKILL.md").write_text("edited after the run\n")
        self.assertEqual(gate.check_change(self.repo, "main").state, gate.State.MISSING)

    def test_a_docs_only_commit_after_the_run_does_not_invalidate_it(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        self.write_passing_report()
        commit_file(self.repo, "docs/guide.md", "words\n")
        self.assertEqual(gate.check_change(self.repo, "main").state, gate.State.PASS)

    def test_an_edited_transcript_fails_it(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        self.write_passing_report()
        (self.repo / ".eval-results" / "run-1" / "t.jsonl").write_text("{\"forged\": true}\n")
        verdict = gate.check_change(self.repo, "main")
        self.assertEqual(verdict.state, gate.State.FAIL)
        self.assertIn("was edited", verdict.reason)

    def test_an_unreadable_report_is_missing(self) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        path = self.write_passing_report()
        path.write_text("not json")
        self.assertEqual(gate.check_change(self.repo, "main").state, gate.State.MISSING)

    def test_the_suite_digest_covers_evals_and_the_evals_definitions_and_nothing_else_in_spec(self) -> None:
        _, before = gate.current(self.repo)
        commit_file(self.repo, "spec/plugin.md", "a requirement\n")
        self.assertEqual(gate.current(self.repo)[1], before)
        commit_file(self.repo, "spec/plugin-evals.md", "an eval\n")
        changed = gate.current(self.repo)[1]
        self.assertNotEqual(changed, before)
        commit_file(self.repo, "evals/cases/c/case.toml", "x = 2\n")
        self.assertNotEqual(gate.current(self.repo)[1], changed)

    def test_an_untracked_new_skill_counts_as_a_steering_change(self) -> None:
        (self.repo / "skills" / "b").mkdir()
        (self.repo / "skills" / "b" / "SKILL.md").write_text("new\n")
        self.assertEqual(gate.check_change(self.repo, "main").state, gate.State.MISSING)

    def test_ignored_files_are_not_part_of_the_digest(self) -> None:
        (self.repo / ".gitignore").write_text("skills/a/scratch.txt\n")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        before = gate.current(self.repo)
        (self.repo / "skills" / "a" / "scratch.txt").write_text("noise\n")
        self.assertEqual(gate.current(self.repo), before)

    def test_evidence_and_the_hook_log_are_never_a_change(self) -> None:
        (self.repo / ".eval-results" / "gate").mkdir(parents=True)
        (self.repo / ".eval-results" / "gate" / "a.json").write_text("{}")
        (self.repo / ".asdlc").mkdir()
        (self.repo / ".asdlc" / "hooks.jsonl").write_text("{}\n")
        base = gate.resolve_base(self.repo, "main")
        self.assertEqual(gate.changed_since(self.repo, base), [])
        self.assertEqual(gate.check_change(self.repo, "main").state, gate.State.NOT_NEEDED)

    def test_no_base_is_unknown_and_says_so_never_a_pass(self) -> None:
        git(self.repo, "branch", "-m", "work", "trunk")
        git(self.repo, "branch", "-D", "main")
        verdict = gate.check_change(self.repo)
        self.assertEqual(verdict.state, gate.State.UNKNOWN)
        self.assertFalse(verdict.holds)
        self.assertIn("--base", verdict.reason)

    def test_the_script_exits_1_with_the_reason_and_0_when_not_needed(self) -> None:
        commit_file(self.repo, "docs/guide.md", "words\n")
        done = run_script("scripts/gate_evidence.py", "verify", "--base", "main", cwd=self.repo)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "gate evidence not needed: " + done.stdout.split(": ", 1)[1].strip()))
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\nnew\n")
        done = run_script("scripts/gate_evidence.py", "verify", "--base", "main", cwd=self.repo)
        self.assertEqual(done.returncode, 1)
        self.assertIn("gate evidence missing", done.stdout)

    def test_a_bad_command_line_prints_usage_and_exits_2(self) -> None:
        self.assertEqual(run_script("scripts/gate_evidence.py", "frobnicate", cwd=self.repo).returncode, 2)


if __name__ == "__main__":
    unittest.main()
