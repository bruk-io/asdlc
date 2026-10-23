"""A scripted demonstration of asdlc stats by stage, over a two-machine history, with no model calls.

Two engineers, ann and kyle, each on their own machine (test_demo_orchestration.Machine). Over
a Monday and a Tuesday: ann captures an intent (recording when the conversation began), leads
it, writes its spec and two children; she accepts it as the person and archives another
intent. ann's worker builds the size-2 child after her approval; kyle's worker builds the
size-1 child without one. Each reviews the other's work, a review asks for changes and the
worker fixes them with signed commits. Both are merged and marked Done, and on Tuesday a bug
is filed against one of them. An agent on ann's machine is refused twice by the board guard.

Every board change goes through asdlc, at a time the script sets (GIT_COMMITTER_DATE), so the
numbers are the same on every run. kyle's clock runs two minutes fast, as a real machine's
might: every commit time from his machine is two minutes late, and the numbers that span both
machines show it (see "What the numbers mean" in docs/guide.md).

Run it with ASDLC_DEMO=1 to print `asdlc stats` on ann's machine; the pull request quotes it.
"""

import json
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests import test_demo_orchestration as demo
from tests.support import hook_payload, run_script
from tests.test_asdlc import BACKLOG, needs_backlog

SAY = bool(os.environ.get("ASDLC_DEMO"))
MONDAY = datetime(2026, 10, 19, tzinfo=UTC)
SKEW = {"ann": timedelta(), "kyle": timedelta(minutes=2)}  # kyle's clock runs two minutes fast
CHECK = ("python3", "-c", "import ast; ast.parse(open('login.py').read())")


def at(hour: int, minute: int = 0, day: int = 0) -> datetime:
    return MONDAY + timedelta(days=day, hours=hour, minutes=minute)


@needs_backlog
class StatsByStageTest(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.root = Path(handle.name).resolve()
        board_origin = self._origins()
        self.ann = demo.Machine(self.root, "ann", board_origin)
        self.kyle = demo.Machine(self.root, "kyle", board_origin)
        self.api = {m.name: m.clone_code(self.root / "origins" / "acme" / "api.git", "api") for m in (self.ann, self.kyle)}

    def _origins(self) -> Path:
        """A bare board with both engineers' preferences and the acme-api project, and a bare acme/api."""
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Seed",
               "GIT_AUTHOR_EMAIL": "seed@example.com", "GIT_COMMITTER_NAME": "Seed", "GIT_COMMITTER_EMAIL": "seed@example.com",
               "GIT_COMMITTER_DATE": (MONDAY + timedelta(hours=8)).isoformat(), "GIT_AUTHOR_DATE": (MONDAY + timedelta(hours=8)).isoformat()}

        def git(*args: str) -> None:
            subprocess.run(["git", *args], check=True, capture_output=True, env=env)

        board = self.root / "origins" / "board.git"
        git("init", "--quiet", "--bare", "-b", "main", str(board))
        seed = self.root / "seed-board"
        done = run_script("scripts/asdlc", "init-board", str(seed), env={**env, "ASDLC_BACKLOG": BACKLOG or "backlog"})
        self.assertEqual(done.returncode, 0, done.stderr)
        (seed / "devs").mkdir(exist_ok=True)
        (seed / "devs" / "ann.yaml").write_text("name: ann\nprefer: [acme-api]\nworkers: 3\nreview: true\n")
        (seed / "devs" / "kyle.yaml").write_text("name: kyle\nworkers: 3\nreview: true\n")
        config = seed / "backlog" / "config.yml"
        config.write_text(config.read_text() + 'projects: ["acme-api"]\n')
        git("-C", str(seed), "add", ".")
        git("-C", str(seed), "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "-m", "Preferences")
        git("-C", str(seed), "remote", "add", "origin", str(board))
        git("-C", str(seed), "push", "--quiet", "origin", "main")
        origin = self.root / "origins" / "acme" / "api.git"
        git("init", "--quiet", "--bare", "-b", "main", str(origin))
        work = self.root / "seed-api"
        git("clone", "--quiet", str(origin), str(work))
        (work / "login.py").write_text("def login(user):\n    return check(user)\n")
        git("-C", str(work), "add", ".")
        git("-C", str(work), "commit", "--quiet", "-m", "start")
        git("-C", str(work), "push", "--quiet", "origin", "main")
        return board

    def on(self, machine: demo.Machine, when: datetime, *args: str, cwd: Path | None = None, ok: bool = True) -> subprocess.CompletedProcess[str]:
        """An asdlc command on that machine, its board commits stamped by that machine's clock at `when`."""
        stamp = (when + SKEW[machine.name]).isoformat()
        return machine.asdlc(*args, cwd=cwd, env={"GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp}, ok=ok)

    def commit(self, machine: demo.Machine, worktree: Path, text: str, message: str, worker: str | None) -> None:
        """A commit on the task's branch: the worker's carry its trailer; a person's (worker None) doesn't."""
        (worktree / "login.py").write_text(text)
        machine.git(worktree, "add", "login.py")
        machine.git(worktree, "commit", "--quiet", "-m", message, *(("--trailer", f"Asdlc-Worker: {worker}") if worker else ()))

    def check(self, machine: demo.Machine, when: datetime, task_id: str, worker: str, worktree: Path, ok: bool = True) -> None:
        done = self.on(machine, when, "record-check", task_id, "--as", worker, "--", *CHECK, cwd=worktree, ok=False)
        self.assertEqual(done.returncode == 0, ok, done.stderr)

    def refuse(self, machine: demo.Machine, cwd: Path, command: str) -> None:
        """An agent on the machine runs a command the board guard refuses; the refusal goes in the board clone's decision log."""
        done = run_script("hooks/guard_board.py", stdin=hook_payload(cwd, "Bash", command=command), cwd=cwd,
                          env={**machine.env, "CLAUDE_PROJECT_DIR": str(machine.board)})
        self.assertIn('"permissionDecision": "deny"', done.stdout, done.stdout + done.stderr)

    def test_two_days_on_two_machines(self) -> None:
        ann, kyle = self.ann, self.kyle

        # Plan: an intent from a conversation that began at 09:00, and one that is dropped.
        created = self.on(ann, at(9, 12), "board", "task", "create", "Rate limit the login endpoint", "--draft", "--type", "intent",
                          "--ac", "Ten failed logins in a minute lock the account for a minute", "-d", "Requested by @ann.\n\n## Problem\n\nBrute force.")
        self.assertIn("DRAFT-1", created.stdout)
        self.on(ann, at(9, 12), "intent-started", "DRAFT-1", "--at", at(9).isoformat())
        self.on(ann, at(9, 20), "board", "task", "create", "Dark mode", "--draft", "--type", "intent")
        self.on(ann, at(9, 25), "lead", "DRAFT-1", "--as", "ann.lead")

        # Design: the spec, linked, then the intent changed once after it.
        self.assertIn("doc-1", self.on(ann, at(9, 40), "board", "doc", "create", "Spec: Rate limit the login endpoint", "-t", "specification").stdout)
        self.on(ann, at(9, 41), "board", "draft", "edit", "DRAFT-1", "--add-doc", "doc-1")
        self.on(ann, at(9, 50), "board", "draft", "edit", "DRAFT-1", "-d", "Requested by @ann.\n\n## Problem\n\nBrute force, from one address or many.")
        self.on(ann, at(10), "board", "task", "create", "Limit failed logins", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-2")
        self.on(ann, at(10), "board", "task", "create", "Log limited logins", "--draft", "-p", "DRAFT-1", "--project", "acme-api", "-l", "size-1")
        accepted = json.loads(self.on(ann, at(10, 30), "accept", "DRAFT-1", "--json").stdout)["accepted"]
        limit, log = accepted["DRAFT-3"], accepted["DRAFT-4"]
        self.on(ann, at(10, 35), "board", "draft", "archive", "DRAFT-2")

        # Build: ann's worker on the size-2 task, kyle's on the size-1 task.
        limit_tree = Path(json.loads(self.on(ann, at(11), "claim", limit, "--as", "ann.w1", "--json").stdout)["worktree"])
        log_tree = Path(json.loads(self.on(kyle, at(11, 1), "claim", log, "--as", "kyle.w1", "--json").stdout)["worktree"])
        self.on(ann, at(11, 10), "board", "task", "edit", limit, "--plan", "Files: login.py. Order: count failures, then lock. Proof: it parses.")
        self.on(kyle, at(11, 10), "board", "task", "edit", log, "--plan", "1. Add a log line to login.py.\n2. Record the check.")
        self.on(kyle, at(11, 12), "board", "task", "edit", log, "--append-notes", "size-1: plan approval skipped; small because it is one log line")
        self.check(kyle, at(11, 15), log, "kyle.w1", log_tree)
        (log_tree / "login.py").write_text("def login(user:\n")
        self.check(kyle, at(11, 20), log, "kyle.w1", log_tree, ok=False)
        self.commit(kyle, log_tree, "def login(user):\n    log(user)\n    return check(user)\n", "Log limited logins", "kyle.w1")
        self.check(kyle, at(11, 25), log, "kyle.w1", log_tree)
        kyle.git(log_tree, "push", "--quiet", "-u", "origin", "HEAD")
        self.on(kyle, at(11, 30), "finish", log, "--as", "kyle.w1", "--pr", "https://github.com/acme/api/pull/2", "--notes", "One log line; checks above.")
        self.on(ann, at(11, 20), "board", "doc", "update", "doc-1", "--content", "R1. Ten failures in a minute lock the account. R2. Log each lock.")
        self.on(ann, at(11, 30), "approve", limit)
        self.check(ann, at(11, 31), limit, "ann.w1", limit_tree)
        self.commit(ann, limit_tree, "def login(user):\n    limit(user)\n    return check(user)\n", "Limit failed logins", "ann.w1")
        self.check(ann, at(11, 50), limit, "ann.w1", limit_tree)
        ann.git(limit_tree, "push", "--quiet", "-u", "origin", "HEAD")
        self.on(ann, at(12), "finish", limit, "--as", "ann.w1", "--pr", "https://github.com/acme/api/pull/1", "--notes", "Limited; checks above.")

        # Deploy: each reviews the other's work; one review asks for changes, fixed by the worker alone.
        self.assertEqual(json.loads(self.on(ann, at(11, 40), "review-next", "--as", "ann.r1", "--json").stdout)["task"], log)
        self.on(ann, at(11, 55), "review-done", log, "--as", "ann.r1", "--verdict", "clean", "--findings", "important=0,nit=1", "--policy", "naming",
                "--plan-matched", "yes", "--notes", "[Compliance, Nit] login.py:2 log() could say what it logs.")
        self.assertEqual(json.loads(self.on(kyle, at(12, 20), "review-next", "--as", "kyle.r1", "--json").stdout)["task"], limit)
        self.on(kyle, at(12, 45), "review-done", limit, "--as", "kyle.r1", "--verdict", "changes", "--findings", "important=1,nit=2",
                "--policy", "testing", "--policy", "review", "--plan-matched", "yes",
                "--notes", "[Bugs, Important] login.py:2 limit(user) counts successful logins too.")
        self.commit(ann, limit_tree, "def login(user):\n    ok = check(user)\n    if not ok:\n        limit(user)\n    return ok\n", "Count failures only", "ann.w1")
        self.check(ann, at(13, 10), limit, "ann.w1", limit_tree)
        ann.git(limit_tree, "push", "--quiet", "origin", "HEAD")
        self.on(ann, at(13, 15), "finish", limit, "--as", "ann.w1", "--notes", "Fixed: failures only. Checks above.")
        self.assertEqual(json.loads(self.on(kyle, at(13, 30), "review-next", "--as", "kyle.r1", "--json").stdout)["task"], limit)
        self.on(kyle, at(13, 40), "review-done", limit, "--as", "kyle.r1", "--verdict", "clean", "--findings", "important=0,nit=0",
                "--plan-matched", "yes", "--notes", "No findings.")
        self.on(kyle, at(14), "board", "task", "edit", log, "-s", "Done")
        self.on(ann, at(15), "board", "task", "edit", limit, "-s", "Done")

        # Tuesday: a bug against a Done task; and an agent on ann's machine refused twice.
        self.on(kyle, at(10, day=1), "board", "task", "create", "Locked logins log the user's email", "--type", "bug", "--ref", log,
                "-l", "size-1", "--project", "acme-api")
        self.refuse(ann, ann.board, "asdlc accept DRAFT-9")
        self.refuse(ann, limit_tree, "git push --force origin HEAD")

        report = json.loads(self.on(ann, at(12, day=1), "stats", "--json").stdout)
        text = self.on(ann, at(12, day=1), "stats").stdout
        stage = {name: found["metrics"] for name, found in report["stages"].items()}
        minutes = lambda key, stage_name, field="median": stage[stage_name][key][field] / 60  # noqa: E731

        self.assertEqual(report["tasks"], {"claimed": 2, "in_review": 0, "done": 2})
        plan = stage["plan"]
        self.assertEqual((plan["conversation_to_intent"]["count"], minutes("conversation_to_intent", "plan")), (1, 12))
        self.assertEqual(plan["conversation_to_intent"]["unrecorded"], ["DRAFT-2"])
        self.assertEqual((plan["survival_rate"]["count"], plan["survival_rate"]["of"], plan["survival_rate"]["archived"]), (1, 2, 1))
        self.assertEqual(plan["post_spec_churn"]["commits"], 1)
        self.assertEqual(minutes("accept_wait", "plan"), 78)
        self.assertEqual(minutes("intent_to_spec", "design"), 28)
        self.assertEqual(stage["design"]["spec_rework"]["commits"], 1)
        build = stage["build"]
        self.assertEqual((build["first_pass_merge"]["count"], build["first_pass_merge"]["of"]), (1, 2))
        self.assertEqual((minutes("approval_to_merge", "build"), build["approval_to_merge"]["sources"]), (210, {"Done commit": 1}))
        self.assertEqual(build["rework_cycles"]["round_trips"], 1)
        self.assertEqual((build["plan_matched"]["count"], build["plan_matched"]["of"]), (3, 3))
        self.assertEqual(minutes("approval_wait", "build"), 20)
        self.assertEqual(build["size1_skipped_approval"]["tasks"], [{"id": log, "noted": True}])
        self.assertEqual(build["parallel_claims"]["by_engineer"], {"ann": {"peak": 1, "median": 1}, "kyle": {"peak": 1, "median": 1}})
        test = stage["test"]
        self.assertEqual((test["first_pass_checks"]["count"], test["first_pass_checks"]["of"]), (1, 2))
        self.assertEqual((test["failed_checks"]["count"], test["failed_checks"]["of"]), (1, 6))
        deploy = stage["deploy"]
        self.assertEqual((minutes("time_to_first_review", "deploy"), deploy["time_to_first_review"]["count"]), (17, 3))
        self.assertEqual((deploy["worker_only_fixes"]["count"], deploy["worker_only_fixes"]["of"]), (1, 1))
        self.assertEqual((deploy["defects_caught"]["important"], deploy["defects_caught"]["nits"]), (1, 3))
        self.assertEqual(sorted(deploy["findings_by_policy"]["by_policy"]), ["naming", "review", "testing"])
        self.assertEqual([b["refs"] for b in deploy["defects_escaped"]["bugs"]], [[log]])
        self.assertEqual(deploy["guard_refusals"]["by_rule"], {"accept": 1, "force push": 1})
        self.assertFalse(stage["test"]["eval_pass_rate"]["measured"])
        self.assertFalse(stage["maintain"]["closing_the_loop"]["measured"])
        self.assertEqual(len(report["not_measurable"]), 4)
        self.assertIn("Not measurable from the board", text)
        if SAY:
            print(f"\n$ asdlc stats   # on ann's machine, Tuesday at noon; kyle's clock runs two minutes fast\n{text.rstrip()}", flush=True)


if __name__ == "__main__":
    unittest.main()
