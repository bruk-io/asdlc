"""The eval runner's pure parts, on recorded transcripts and fixed board histories, and the few
shell pieces whose mistakes would grade a trial wrongly (a forced push missed, the suite
handed to the agent). The cases themselves are proven by `scripts/eval validate`, which
`./scripts/check` runs."""

import contextlib
import io
import json
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, commit_file, git, load, make_repo, run_script

load("scripts/protected_paths.py")  # scripts/gate_evidence.py imports it from beside itself
gate_evidence = load("scripts/gate_evidence.py")  # scripts/eval imports it from beside itself
ev = load("scripts/eval")

CASE = """
source = "The owner"
kind = "outcome"
suite = "regression"
description = "A small request stays small."
checks = ["it_changed"]

[run]
model = "sonnet"
max_turns = 15

[[sessions]]
prompt = "Set {thing} to 15m."
"""

# A session as `claude -p --output-format stream-json --verbose` writes it (Claude Code 2.1.309):
# init, the main agent's calls, a foreground subagent's call (parent_tool_use_id set), the same
# message id twice (one line per content block), a failing call, and the result with its usage.
RECORDED = [
    {"type": "system", "subtype": "hook_started", "session_id": "s-1"},
    {"type": "system", "subtype": "init", "session_id": "s-1", "model": "claude-sonnet-5-5", "tools": ["Bash", "Skill", "Task"]},
    {"type": "assistant", "session_id": "s-1", "parent_tool_use_id": None, "message": {
        "id": "m1", "model": "claude-sonnet-5-5", "usage": {"input_tokens": 3, "output_tokens": 40, "cache_read_input_tokens": 1000,
                                                             "cache_creation_input_tokens": 500, "cache_creation": {"ephemeral_1h_input_tokens": 500}},
        "content": [{"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "asdlc:orchestrate"}}]}},
    {"type": "user", "session_id": "s-1", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Launching skill"}]}},
    {"type": "assistant", "session_id": "s-1", "message": {
        "id": "m2", "model": "claude-sonnet-5-5", "usage": {"input_tokens": 2, "output_tokens": 30},
        "content": [{"type": "text", "text": "Claiming work."}]}},
    {"type": "assistant", "session_id": "s-1", "message": {
        "id": "m2", "model": "claude-sonnet-5-5", "usage": {"input_tokens": 2, "output_tokens": 30},
        "content": [{"type": "tool_use", "id": "t2", "name": "Task", "input": {"subagent_type": "asdlc:worker", "model": "sonnet", "prompt": "plan"}}]}},
    {"type": "assistant", "session_id": "s-1", "parent_tool_use_id": "t2", "message": {
        "id": "m3", "model": "claude-haiku-5-5", "usage": {"input_tokens": 10, "output_tokens": 5},
        "content": [{"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "asdlc record-check TASK-1 --as kyle.w1 -- make test"}}]}},
    {"type": "user", "session_id": "s-1", "parent_tool_use_id": "t2", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t3", "is_error": True, "content": [{"type": "text", "text": "TASK-1's plan isn't approved"}]}]}},
    {"type": "rate_limit_event", "session_id": "s-1"},
    "not json at all",
    {"type": "result", "subtype": "success", "is_error": False, "session_id": "s-1", "num_turns": 4, "duration_ms": 6128,
     "total_cost_usd": 0.0779611, "result": "Plans wait for you: asdlc approve TASK-1", "permission_denials": [{"tool_name": "Bash"}],
     "usage": {"input_tokens": 6, "output_tokens": 279, "cache_read_input_tokens": 35111, "cache_creation_input_tokens": 17912,
               "cache_creation": {"ephemeral_1h_input_tokens": 17912, "ephemeral_5m_input_tokens": 0}},
     "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 6, "outputTokens": 279, "cacheReadInputTokens": 35111,
                                          "cacheCreationInputTokens": 17912, "costUSD": 0.0779611}}},
]

TASK = """---
id: TASK-1
title: Count failed logins
status: In Progress
assignee:
  - '@ann.w1'
labels:
  - size-2
  - changes-requested
dependencies: []
type: task
project: acme-api
asdlc_review_findings: important=1,nit=0
asdlc_review_policies: [review]
---

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Count in login().
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-23T05:00:00Z

---

Review by @kyle.r1 (cross-machine): changes requested.

---
<!-- COMMENTS:END -->
"""


def _lines(records: list[object]) -> list[str]:
    return [r if isinstance(r, str) else json.dumps(r) for r in records]


def _trial(case: str, passed: bool, suite: str = "regression", tokens: dict[str, object] | None = None) -> object:
    usage = {model: ev.Usage(**numbers) for model, numbers in (tokens or {}).items()}
    counts = ev.Counts(usage, 3, 2, 0, 1000, 0.01, 0, 1, 1)
    return ev.TrialResult(case, "outcome", suite, 1, passed, (ev.CheckResult("c", passed, ""),), counts, "with-plugin", "sonnet", "abc")


class ParseCaseTest(unittest.TestCase):
    def test_a_complete_case(self) -> None:
        case = ev.parse_case(CASE, "small")
        self.assertEqual((case.kind, case.suite, case.checks, case.model, case.max_turns), ("outcome", "regression", ("it_changed",), "sonnet", 15))
        self.assertEqual(case.runs, (ev.Session("Set {thing} to 15m."),))
        self.assertEqual(case.arms, (ev.Arm.WITH_PLUGIN, ev.Arm.WITHOUT_SKILLS))

    def test_every_problem_is_named_at_once(self) -> None:
        with self.assertRaises(ev.CaseError) as raised:
            ev.parse_case('kind = "vibes"\nsuite = "x"\nflavour = 1\n[run]\npermission_mode = "bypassPermissions"\n', "bad")
        message = str(raised.exception)
        for words in ("source is required", "kind must be", "suite must be", "unknown key 'flavour'", "checks must name",
                      "sessions or items", "bypassPermissions is never used"):
            self.assertIn(words, message)

    def test_person_steps_come_between_sessions(self) -> None:
        text = CASE.replace('[[sessions]]\nprompt = "Set {thing} to 15m."', '[[sessions]]\nprompt = "x"\nbefore = ["approve"]')
        with self.assertRaises(ev.CaseError) as raised:
            ev.parse_case(text, "early")
        self.assertIn("session 1 can't have person steps", str(raised.exception))

    def test_a_trigger_set_runs_each_item_fresh(self) -> None:
        text = CASE.split("[[sessions]]")[0] + '[[items]]\nprompt = "Work the board."\nexpect = "orchestrate"\n[[items]]\nprompt = "Hi"\nexpect = "none"\n'
        case = ev.parse_case(text, "triggers")
        self.assertEqual([s.fresh for s in case.runs], [True, True])
        self.assertEqual(case.items[0].expect, "orchestrate")

    def test_prompts_are_filled_from_the_fixture(self) -> None:
        self.assertEqual(ev.fill("Set {thing} to 15m.", {"thing": "review_fallback_after"}), "Set review_fallback_after to 15m.")
        with self.assertRaises(ev.CaseError):
            ev.fill("{missing}", {})


class ParseStreamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = ev.parse_stream(_lines(RECORDED), 0)

    def test_events_in_order_with_subagent_calls_marked(self) -> None:
        kinds = [(e.kind, e.name, e.parent) for e in self.stream.events]
        self.assertEqual(kinds, [("tool", "Skill", ""), ("result", "Skill", ""), ("text", "", ""), ("tool", "Task", ""),
                                 ("tool", "Bash", "t2"), ("result", "Bash", "t2"), ("end", "", "")])
        self.assertEqual(self.stream.session_id, "s-1")
        self.assertTrue(self.stream.events[5].error)
        self.assertIn("isn't approved", self.stream.events[5].text)

    def test_counts_come_from_the_result_with_the_cache_split(self) -> None:
        usage = self.stream.tokens["claude-sonnet-5-5"]
        self.assertEqual(usage, ev.Usage(6, 279, 35111, 17912, 500))
        tally = ev.counts([self.stream], self.stream.events)
        self.assertEqual((tally.turns, tally.tool_calls, tally.tool_errors, tally.permission_denials, tally.finished), (4, 3, 1, 1, 1))
        self.assertEqual(ev.counts_from_json(json.loads(json.dumps(ev.counts_json(tally)))), tally)

    def test_a_session_without_a_result_is_counted_from_its_messages_once_each(self) -> None:
        cut = ev.parse_stream(_lines(RECORDED[:-1]), 0)
        self.assertIsNone(cut.result)
        self.assertEqual(cut.tokens["claude-sonnet-5-5"], ev.Usage(5, 70, 1000, 500, 500))
        self.assertEqual(cut.tokens["claude-haiku-5-5"], ev.Usage(10, 5))
        self.assertNotIn("end", [e.kind for e in cut.events])

    def test_a_resumed_session_counts_only_its_own_share(self) -> None:
        # Recorded from a resumed session: modelUsage and total_cost_usd carried the whole conversation,
        # model_usage_since_last_result this run's share.
        result = {**RECORDED[-1], "total_cost_usd": 0.5023830, "modelUsage": {"claude-sonnet-5-5": {
            "inputTokens": 118, "outputTokens": 18230, "cacheReadInputTokens": 1145190, "cacheCreationInputTokens": 66830, "costUSD": 0.502383}},
            "model_usage_since_last_result": {"claude-sonnet-5-5": {"inputTokens": 68, "outputTokens": 9252, "cacheReadInputTokens": 746060,
                                                                     "cacheCreationInputTokens": 20047, "costUSD": 0.2278975}}}
        resumed = ev.parse_stream(_lines([*RECORDED[:-1], result]), 1)
        self.assertEqual(resumed.tokens["claude-sonnet-5-5"].cache_write, 20047)
        self.assertAlmostEqual(resumed.cli_cost_usd, 0.2278975)

    def test_skills_and_commands_read_from_the_events(self) -> None:
        self.assertEqual(ev.skills_loaded(self.stream.events), ("orchestrate",))
        self.assertEqual(ev.skill_name("/asdlc:capture-intent and more"), "capture-intent")
        self.assertEqual(ev.commands(self.stream.events), ("asdlc record-check TASK-1 --as kyle.w1 -- make test",))
        self.assertEqual(ev.first(self.stream.events, ev.runs_command(r"record-check")), 4)

    def test_commands_run_are_told_from_words_in_their_arguments(self) -> None:
        building = ev.runs_program(r"asdlc\s+record-check\b|git\b[^|;&]*?\s(commit|push)\b")

        def bash(command: str) -> object:
            return ev.Event(0, "tool", "Bash", {"command": command})

        for command in ("cd /w && asdlc record-check TASK-1 --as k -- make test", "X=1 git -C /w push -u origin HEAD",
                        "make test 2>&1 | tail -8; git add a && git commit -qm 'm'"):
            self.assertTrue(building(bash(command)), command)
        for command in ("asdlc board task edit TASK-1 --plan \"1. asdlc record-check, then git push\"",
                        "asdlc board task edit TASK-2 --plan \"$(cat <<'EOF'\n## Proof\n- git commit and asdlc record-check\nEOF\n)\""):
            self.assertFalse(building(bash(command)), command)
        self.assertEqual(ev.shell_segments("cd /w && git -C /w commit -m 'a; b'"), ("cd /w", "git -C /w commit -m ''"))

    def test_subagent_transcripts_add_only_calls_the_stream_missed(self) -> None:
        extra = [ev.Event(-1, "tool", "Bash", {"command": "ls"}, "t3"), ev.Event(-1, "tool", "Edit", {"file_path": "/w/x"}, "t9")]
        merged = ev.merge_subagent_events(self.stream.events, extra)
        self.assertEqual(len(merged), len(self.stream.events) + 1)
        self.assertTrue(ev.edits_under("/w")(merged[-1]))
        self.assertFalse(ev.edits_under("/w2")(merged[-1]))


class BoardTest(unittest.TestCase):
    def test_reads_what_backlog_writes(self) -> None:
        item = ev.board_item("backlog/tasks/task-1 - Count.md", TASK)
        self.assertEqual((item.id, item.status, item.assignees, item.labels), ("TASK-1", "In Progress", ("@ann.w1",), ("size-2", "changes-requested")))
        self.assertEqual(item.key("asdlc_review_policies"), "review")
        self.assertEqual(item.section("PLAN"), "1. Count in login().")
        self.assertIn("Review by @kyle.r1", item.section("COMMENTS"))
        self.assertFalse(item.draft)
        self.assertIsNone(ev.board_item("x.md", "no frontmatter"))

    def test_person_steps_mark_the_board_they_saw(self) -> None:
        commits = tuple(ev.BoardCommit(f"c{n}", "", "", {}) for n in range(4))
        events = (ev.Event(0, "tool", "Bash"), ev.Event(1, "person", "approve", board_commits=2), ev.Event(1, "tool", "Bash"))
        found = ev.Outcome({}, commits, {}, {}, (), (), {}, events, ())
        self.assertEqual([c.sha for c in ev.board_commits_before(found, "approve")], ["c0", "c1"])
        self.assertEqual(ev.person_index(events, "approve"), 1)
        self.assertEqual(ev.outcome_from_json(json.loads(json.dumps(ev.outcome_json(found)))), found)


class ChecksTest(unittest.TestCase):
    def test_a_check_that_raises_fails(self) -> None:
        case = ev.parse_case(CASE, "small")
        found = ev.Outcome({}, (), {}, {}, (), (), {}, (), ())
        results = ev.run_checks(found, case, lambda name: lambda o, c: {}["boom"])
        self.assertEqual((results[0].passed, results[0].detail), (False, "the check raised KeyError: 'boom'"))

    def test_validation_needs_a_passing_reference_and_a_failing_null(self) -> None:
        ok, bad = ev.CheckResult("a", True, ""), ev.CheckResult("a", False, "no")
        self.assertEqual(ev.validation_problems("x", [ok], [bad]), [])
        self.assertIn("the reference run fails a: no", ev.validation_problems("x", [bad], [bad])[0])
        self.assertIn("can't tell doing nothing", ev.validation_problems("x", [ok], [ok])[0])


class StatisticsTest(unittest.TestCase):
    def test_pass_at_k_and_pass_hat_k(self) -> None:
        self.assertEqual(ev.pass_at_k(3, 1, 3), 1.0)
        self.assertEqual(ev.pass_at_k(3, 0, 3), 0.0)
        self.assertAlmostEqual(ev.pass_at_k(4, 1, 2), 0.5)
        self.assertEqual(ev.pass_hat_k(3, 3, 3), 1.0)
        self.assertEqual(ev.pass_hat_k(3, 2, 3), 0.0)
        self.assertAlmostEqual(ev.pass_hat_k(4, 3, 2), 0.5)

    def test_clustered_standard_error(self) -> None:
        # Mean 0.5; case one's deviations sum to +1, case two's to -1: sqrt(1 + 1) / 4.
        self.assertAlmostEqual(ev.clustered_se([[1.0, 1.0], [0.0, 0.0]]), math.sqrt(2) / 4)
        self.assertEqual(ev.clustered_se([[1.0, 1.0], [1.0]]), 0.0)
        self.assertAlmostEqual(ev.detectable(0.1), 2.8 * math.sqrt(2) * 0.1)

    def test_cost_at_the_table_s_prices(self) -> None:
        version, prices = ev.parse_prices((ROOT / "evals" / "prices.toml").read_text())
        self.assertRegex(version, r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(ev.price_for("claude-sonnet-5-5-20261001", prices).model, "claude-sonnet-5-5")
        self.assertEqual(ev.price_for("claude-opus-5-20260101", prices).model, "claude-opus-5")
        recorded = ev.parse_stream(_lines(RECORDED), 0)
        dollars, unknown = ev.cost(recorded.tokens, prices)
        self.assertEqual(unknown, ())
        # Claude Code's own figure for the recorded session was 0.0779611 when all of its writes were 1-hour ones.
        whole = {"claude-sonnet-5-5": ev.Usage(6, 279, 35111, 17912, 17912)}
        self.assertAlmostEqual(ev.cost(whole, prices)[0], 0.0779611, places=6)
        self.assertLess(dollars, 0.0779611)
        self.assertEqual(ev.cost({"claude-new-9": ev.Usage(1, 1)}, prices), (0.0, ("claude-new-9",)))

    def test_summary_and_report(self) -> None:
        _, prices = ev.parse_prices((ROOT / "evals" / "prices.toml").read_text())
        tokens = {"claude-sonnet-5-5": {"input": 1_000_000}}
        trials = [_trial("a", True, tokens=tokens), _trial("a", False), _trial("b", True, "capability"), _trial("b", True, "capability")]
        summary = ev.summarise(trials, prices)
        self.assertEqual(summary["cases"]["a"]["passed"], 1)
        self.assertEqual(summary["cases"]["a"]["failing_checks"], {"c": 1})
        self.assertAlmostEqual(summary["cases"]["a"]["cost_usd"], 2.0)
        self.assertEqual(summary["overall"]["all"]["trials"], 4)
        self.assertAlmostEqual(summary["overall"]["all"]["mean"], 0.75)
        self.assertEqual(summary["overall"]["capability"]["detectable"], None)
        text = "\n".join(ev.report_lines(summary, {"run": "r", "plugin": "abc"}, "v1", [(trials[1], ["[end] done"])]))
        self.assertIn("| a | outcome | regression | 1/2 |", text)
        self.assertIn("Smallest change two runs of this size can detect", text)
        self.assertIn("$2.0000", text)
        self.assertIn("### a trial 1: FAILED: c", text)

    def test_the_sample_shows_failures_first_then_a_few_passes(self) -> None:
        trials = [_trial("a", False), _trial("a", False), _trial("b", False), _trial("c", True), _trial("d", True)]
        chosen = ev.sample(trials, failing=2, passing=1)
        self.assertEqual([(t.case, t.passed) for t in chosen], [("a", False), ("b", False), ("c", True)])

    def test_key_moments(self) -> None:
        events = (ev.Event(0, "tool", "Skill", {"skill": "asdlc:orchestrate"}), ev.Event(0, "tool", "Read", {"file_path": "x"}),
                  ev.Event(1, "person", "approve", text="asdlc approve TASK-1"), ev.Event(1, "tool", "Bash", {"command": "git -C w push origin HEAD"}),
                  ev.Event(1, "end", text="Both in review."))
        self.assertEqual(ev.key_moments(events), ["[skill] asdlc:orchestrate", "[person] approve: asdlc approve TASK-1",
                                                  "[bash] git -C w push origin HEAD", "[end] Both in review."])


class AgentSettingsTest(unittest.TestCase):
    def test_no_web_no_suite_and_a_strict_sandbox_in_the_container(self) -> None:
        options = ev.Options(deny_read=("/repo",))
        native = ev.agent_settings(options, container=False, sandbox_available=False)
        self.assertEqual(native["permissions"]["deny"], ["WebFetch", "WebSearch", "Read(//repo/**)"])
        self.assertNotIn("sandbox", native)
        boxed = ev.agent_settings(options, container=True, sandbox_available=True)["sandbox"]
        self.assertTrue(boxed["failIfUnavailable"] and boxed["enabled"] and not boxed["allowUnsandboxedCommands"])
        self.assertEqual(boxed["network"], {"allowedDomains": [], "strictAllowlist": True})
        self.assertFalse(boxed["autoAllowBashIfSandboxed"])

    def test_the_command_line(self) -> None:
        case = ev.parse_case(CASE.replace('model = "sonnet"', 'model = "sonnet"\nagent = "asdlc:worker"'), "small")
        words = ev.claude_arguments(case, ev.Options(model="opus"), "do it", "s-1", Path("/release"), Path("/s.json"))
        self.assertEqual(words[:2], ["-p", "do it"])
        for pair in (["--plugin-dir", "/release"], ["--model", "opus"], ["--agent", "asdlc:worker"], ["--resume", "s-1"],
                     ["--output-format", "stream-json"], ["--permission-prompts", "none"], ["--max-turns", "15"]):
            self.assertIn(pair, [words[n:n + 2] for n in range(len(words))])
        self.assertNotIn("--resume", ev.claude_arguments(case, ev.Options(), "do it", "", Path("/r"), Path("/s")))


class ShellTest(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.root = Path(handle.name)
        self.env = {**os.environ, **ev.SEED_ENV}

    def git(self, where: Path, *args: str) -> str:
        return subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True, check=True, env=self.env).stdout.strip()

    def test_a_forced_push_is_seen_and_a_fast_forward_is_not(self) -> None:
        origin = ev.bare(self.root / "origin.git")
        work = self.root / "work"
        subprocess.run(["git", "clone", "--quiet", str(origin), str(work)], check=True, capture_output=True, env=self.env)
        (work / "a").write_text("a")
        self.git(work, "add", "a")
        self.git(work, "commit", "-qm", "a")
        self.git(work, "push", "-q", "origin", "HEAD:main", "HEAD:topic")
        baseline = ev.code_refs(origin)
        ev.clear_reflogs(origin)
        (work / "b").write_text("b")
        self.git(work, "add", "b")
        self.git(work, "commit", "-qm", "b")
        self.git(work, "push", "-q", "origin", "HEAD:topic")
        self.git(work, "commit", "-q", "--amend", "-m", "b again")
        self.git(work, "push", "-q", "--force", "origin", "HEAD:topic")
        repo = ev.code_repo(origin, baseline)
        self.assertEqual([u.forced for u in repo.updates], [False, True])
        self.assertEqual(repo.baseline, baseline)
        self.assertEqual(repo.refs["main"], baseline["main"])
        self.assertIn("b again", "".join(repo.messages.values()))

    def test_the_agent_s_plugin_leaves_out_the_suite(self) -> None:
        source = self.root / "source"
        for path in ("skills/a/SKILL.md", "evals/cases/x/case.toml", "tests/test_x.py", "spec/thing-evals.md", "spec/thing.md", "scripts/asdlc"):
            (source / path).parent.mkdir(parents=True, exist_ok=True)
            (source / path).write_text("x")
        target, version = ev.export_plugin(str(source), self.root / "out", ev.Arm.WITH_PLUGIN)
        self.addCleanup(ev.make_writable, self.root / "out")
        kept = sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file())
        self.assertEqual(kept, ["scripts/asdlc", "skills/a/SKILL.md", "spec/thing.md"])
        self.assertEqual((target / "scripts" / "asdlc").stat().st_mode & 0o222, 0)
        bare, _ = ev.export_plugin(str(source), self.root / "out2", ev.Arm.WITHOUT_SKILLS)
        self.addCleanup(ev.make_writable, self.root / "out2")
        self.assertFalse((bare / "skills").exists())

    def test_every_case_definition_parses(self) -> None:
        for folder in sorted((ROOT / "evals" / "cases").iterdir()):
            with self.subTest(case=folder.name):
                case = ev.parse_case((folder / "case.toml").read_text(), folder.name)
                self.assertTrue(case.source)

    def test_regrade_judges_a_stored_outcome_with_the_checks_as_they_are_now(self) -> None:
        trial = self.root / "run" / "small-request-no-intent" / "trial-1"
        trial.mkdir(parents=True)
        settings = 'stale_after = "2h"\nreview_fallback_after = "15m"\n'
        found = ev.Outcome({}, (ev.BoardCommit("c0", "", "", {}),), {}, {}, (), (), {"asdlc.toml": settings}, (), ("done",))
        (trial / "outcome.json").write_text(json.dumps(ev.outcome_json(found)))
        (trial / "session-1.jsonl").write_text("\n".join(_lines(RECORDED)))
        stale = {"case": "small-request-no-intent", "kind": "outcome", "suite": "regression", "trial": 1, "passed": False,
                 "checks": [{"name": "setting_changed", "passed": False, "detail": "an older check"}],
                 "counts": ev.counts_json(ev.Counts({}, 0, 0, 0, 0, 0.0, 0, 1, 1)), "arm": "with-plugin", "model": "sonnet", "plugin": "abc"}
        (trial / "trial.json").write_text(json.dumps(stale))
        done = run_script("scripts/eval", "regrade", str(self.root / "run"))
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads((trial / "trial.json").read_text())
        self.assertTrue(data["passed"])
        self.assertEqual(data["earlier_checks"][0]["checks"][0]["detail"], "an older check")
        self.assertEqual(data["counts"]["tokens"]["claude-sonnet-5-5"]["cache_write"], 17912)

    def test_report_without_results_says_so(self) -> None:
        done = run_script("scripts/eval", "report", str(self.root))
        self.assertEqual(done.returncode, 1)
        self.assertIn("no trials", done.stdout)


class GateTest(unittest.TestCase):
    """`eval gate` on a throwaway repository, with the agents replaced by a function that writes trial results."""

    SUITES = {"keeps-the-gate": "regression", "keeps-the-rule": "regression", "measures-skill": "capability"}

    def setUp(self) -> None:
        handle, self.repo = make_repo()
        self.addCleanup(handle.cleanup)
        commit_file(self.repo, "skills/a/SKILL.md", "---\nname: a\n---\n")
        commit_file(self.repo, "README.md", "hello\n")
        git(self.repo, "branch", "-M", "main")
        git(self.repo, "switch", "-q", "-c", "work")
        self.calls: list[list[str]] = []
        self.passing: dict[str, int] = {}  # a case's passes per trial count; missing means all
        self.during = None

    def fake_run(self, chosen: list[str], trials: int, options: object, plugin_source: str, results: Path) -> Path:
        self.calls.append(list(chosen))
        out = results / f"2026010{len(self.calls)}T000000Z-abc-with-plugin"
        out.mkdir(parents=True)
        (out / "run.json").write_text(json.dumps({"run": out.name, "plugin": "abc", "arm": "with-plugin", "model": "", "where": "native", "trials": trials}))
        for name in chosen:
            for number in range(1, trials + 1):
                where = out / name / f"trial-{number}"
                where.mkdir(parents=True)
                passed = number <= self.passing.get(name, trials)
                checks = [{"name": "the_check", "passed": passed, "detail": "" if passed else "it did not"}]
                (where / "trial.json").write_text(json.dumps({
                    "case": name, "kind": "outcome", "suite": self.SUITES[name], "trial": number, "passed": passed, "checks": checks,
                    "counts": ev.counts_json(ev.Counts({}, 1, 1, 0, 1000, 0.0, 0, 1, 1)), "arm": "with-plugin", "model": "sonnet", "plugin": "abc"}))
                (where / "outcome.json").write_text("{}")
                (where / "session-0.jsonl").write_text("{}\n")
        if self.during:
            self.during()
        return out

    def gate(self, everything: bool = False, suites: dict[str, str] | None = None, base: str = "main") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ev.gate(base, everything, 3, ev.Options(), root=self.repo, suites=suites or self.SUITES, run_cases=self.fake_run)
        return code, out.getvalue(), err.getvalue()

    def edit_skill(self, text: str) -> None:
        commit_file(self.repo, "skills/a/SKILL.md", f"---\nname: a\n---\n{text}\n")

    def test_a_change_with_no_steering_path_runs_nothing(self) -> None:
        commit_file(self.repo, "docs/guide.md", "words\n")
        code, out, _ = self.gate()
        self.assertEqual(code, 0)
        self.assertIn("gate not needed", out)
        self.assertEqual(self.calls, [])

    def test_a_steering_change_runs_the_regression_cases_and_records_passing_evidence(self) -> None:
        self.edit_skill("new")
        code, out, _ = self.gate()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.calls, [["keeps-the-gate", "keeps-the-rule"]])
        self.assertIn("This spends tokens", out)
        self.assertIn("gate passed", out)
        self.assertEqual(gate_evidence.check_change(self.repo, "main").state, gate_evidence.State.PASS)

    def test_a_second_run_for_the_same_content_spends_nothing(self) -> None:
        self.edit_skill("new")
        self.gate()
        code, out, _ = self.gate()
        self.assertEqual(code, 0)
        self.assertIn("already passed", out)
        self.assertEqual(len(self.calls), 1)

    def test_a_failing_regression_case_fails_the_gate_and_the_evidence_says_so(self) -> None:
        self.edit_skill("new")
        self.passing = {"keeps-the-rule": 2}
        code, out, _ = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("keeps-the-rule: 2 of 3 trials passed (failing: the_check x1)", out)
        verdict = gate_evidence.check_change(self.repo, "main")
        self.assertEqual(verdict.state, gate_evidence.State.FAIL)
        self.assertIn("2 of 3 trials passed", verdict.reason)

    def test_a_steering_path_edited_while_the_gate_ran_records_nothing(self) -> None:
        self.edit_skill("new")
        self.during = lambda: (self.repo / "skills" / "a" / "SKILL.md").write_text("edited during the run\n")
        code, _, err = self.gate()
        self.assertEqual(code, 2)
        self.assertIn("changed while the gate ran", err)
        self.assertFalse(list((self.repo / ".eval-results" / "gate").glob("*.json")) if (self.repo / ".eval-results" / "gate").exists() else [])

    def test_a_transcript_edited_after_the_run_voids_the_evidence(self) -> None:
        self.edit_skill("new")
        self.gate()
        next(self.repo.glob(".eval-results/*/keeps-the-gate/trial-1/session-0.jsonl")).write_text("{\"forged\": 1}\n")
        verdict = gate_evidence.check_change(self.repo, "main")
        self.assertEqual(verdict.state, gate_evidence.State.FAIL)
        self.assertIn("was edited", verdict.reason)

    def test_with_no_regression_case_it_refuses_rather_than_pass_untested(self) -> None:
        self.edit_skill("new")
        code, _, err = self.gate(suites={"measures-skill": "capability"})
        self.assertEqual(code, 2)
        self.assertIn("no regression case", err)
        self.assertEqual(self.calls, [])

    def test_no_base_is_refused(self) -> None:
        git(self.repo, "branch", "-m", "work", "trunk")
        git(self.repo, "branch", "-D", "main")
        code, _, err = self.gate(base="")
        self.assertEqual(code, 2)
        self.assertIn("--base", err)

    def test_all_runs_capability_cases_and_a_later_drop_beyond_noise_fails(self) -> None:
        suites = {**self.SUITES, "measures-more": "capability", "measures-again": "capability", "and-again": "capability"}
        self.SUITES = suites
        self.edit_skill("one")
        self.assertEqual(self.gate(everything=True, suites=suites)[0], 0)
        self.passing = {"measures-skill": 0, "measures-more": 0, "measures-again": 0, "and-again": 0}
        self.edit_skill("two")
        code, out, _ = self.gate(everything=True, suites=suites)
        self.assertEqual(code, 1)
        self.assertIn("capability cases fell from 1.00 to 0.00", out)

    def test_the_gate_command_line_refuses_zero_trials(self) -> None:
        done = run_script("scripts/eval", "gate", "--trials", "0", cwd=self.repo)
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
