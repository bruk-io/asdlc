"""A scripted demonstration of cross-machine review, with no model calls.

Two engineers, ann and kyle, each on their own machine (see test_demo_orchestration.Machine):
their own git identity and registry, their own clone of the board and of acme/api. The
worker and the reviewer are played by the script: what an agent would decide is written
here, and every board change goes through asdlc.

Ann's worker finishes a task; Kyle's reviewer claims it, requests changes; Ann's worker
fixes it and submits it again; Kyle's reviewer marks it clean. Then a task nobody reviews
is picked up by its author's machine once it has waited longer than review_fallback_after.

Run it with ASDLC_DEMO=1 to print the story; the pull request quotes that output.
"""

import json
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests import test_demo_orchestration as demo
from tests.support import run_script
from tests.test_asdlc import BACKLOG, needs_backlog

SAY = bool(os.environ.get("ASDLC_DEMO"))


@needs_backlog
class CrossMachineReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.root = Path(handle.name).resolve()
        self.story: list[str] = []
        board_origin = self._origins()
        self.ann = demo.Machine(self.root, "ann", board_origin)
        self.kyle = demo.Machine(self.root, "kyle", board_origin)
        self.api = {m.name: m.clone_code(self.root / "origins" / "acme" / "api.git", "api") for m in (self.ann, self.kyle)}

    def _origins(self) -> Path:
        """A bare board with two accepted tasks in acme-api and both engineers' preferences, and a bare acme/api."""
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Seed",
               "GIT_AUTHOR_EMAIL": "seed@example.com", "GIT_COMMITTER_NAME": "Seed", "GIT_COMMITTER_EMAIL": "seed@example.com"}

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
        (seed / "asdlc.toml").write_text('stale_after = "2h"\nreview_fallback_after = "30m"\n')
        config = seed / "backlog" / "config.yml"
        config.write_text(config.read_text() + 'projects: ["acme-api"]\n')
        hooks_off = {**env, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null"}
        for title in ("Rate limit the login endpoint", "Log failed logins"):
            created = subprocess.run([BACKLOG or "backlog", "task", "create", title, "--type", "task", "-l", "size-2", "--project", "acme-api",
                                      "--ac", "It works"], cwd=seed, capture_output=True, text=True, env=hooks_off)
            self.assertEqual(created.returncode, 0, created.stderr)
        git("-C", str(seed), "add", ".")
        git("-C", str(seed), "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "-m", "Preferences and settings")
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

    def say(self, line: str) -> None:
        self.story.append(line)

    def tearDown(self) -> None:
        if SAY:
            print("\n" + "\n".join(self.story), flush=True)

    # What the worker and the reviewer agents would do, scripted.

    def build(self, machine: demo.Machine, task_id: str, worktree: Path, text: str, message: str) -> str:
        """The worker's build and finish steps: commit, record a check, push the branch."""
        (worktree / "login.py").write_text(text)
        machine.git(worktree, "commit", "--quiet", "-am", message)
        machine.asdlc("record-check", task_id, "--", "python3", "-c", "import ast, sys; ast.parse(open('login.py').read())", cwd=worktree)
        machine.git(worktree, "push", "--quiet", "--force-with-lease", "-u", "origin", "HEAD")
        return machine.git(worktree, "branch", "--show-current")

    def submit(self, machine: demo.Machine, task_id: str, branch: str, number: int, first: bool) -> None:
        refs = ("--add-ref", branch, "--add-ref", f"https://github.com/acme/api/pull/{number}") if first else ("--remove-label", "changes-requested")
        machine.asdlc("board", "task", "edit", task_id, *refs, "-s", "In Review", "--append-notes", "Built; checks recorded above.")

    def diff(self, machine: demo.Machine, claimed: dict[str, object]) -> str:
        """The reviewer's view: the branch against the default branch, fetched, never checked out for editing."""
        repo = Path(str(claimed["repo"]))
        machine.git(repo, "fetch", "--quiet", "origin", str(claimed["branch"]), str(claimed["default_branch"]))
        return machine.git(repo, "diff", f"origin/{claimed['default_branch']}...origin/{claimed['branch']}")

    def task(self, machine: demo.Machine, task_id: str) -> str:
        return machine.asdlc("board", "task", "view", task_id, "--plain").stdout

    def test_review_across_machines_and_the_fallback(self) -> None:
        ann, kyle = self.ann, self.kyle
        self.say("Two machines: ann and kyle, each with a board clone and a registered clone of acme/api; both review (devs/<name>.yaml), "
                 "review_fallback_after 30m (asdlc.toml).")

        # 1. Ann's worker builds TASK-1 and hands it to review.
        claimed = ann.json("next", "--as", "ann.w1")
        self.assertEqual(claimed["task"], "TASK-1")
        worktree = Path(str(claimed["worktree"]))
        branch = self.build(ann, "TASK-1", worktree, "def login(user):\n    limit(user)\n    return check(user)\n", "Rate limit login")
        self.submit(ann, "TASK-1", branch, 1, first=True)
        own = ann.json("review-next", "--as", "ann.r1")
        self.assertFalse(own["claimed"])
        self.say(f"1. ann.w1 claims TASK-1, builds it in {worktree.relative_to(self.root)}, records a check, pushes {branch} and sets it In Review "
                 "with the branch and pull request. ann's own review-next takes nothing: it is her work.")

        # 2. Kyle's reviewer claims it on his machine and requests changes.
        review = kyle.json("review-next", "--as", "kyle.r1")
        self.assertEqual((review["task"], review["kind"], review["branch"], review["model"], review["effort"]),
                         ("TASK-1", "cross-machine", branch, "sonnet", "medium"))
        self.assertEqual(review["repo"], str(self.api["kyle"]))
        diff = self.diff(kyle, review)
        self.assertIn("+    limit(user)", diff)
        busy = kyle.json("mine", "--as", "kyle")
        self.assertEqual(([r["id"] for r in busy["reviews"]], busy["tasks"]), (["TASK-1"], []))
        findings = "[Bugs, Important] login.py:2 limit(user) runs before check(user), so failed and successful logins count alike; count failures only."
        sent = kyle.json("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "changes", "--notes", findings)
        self.assertEqual((sent["status"], sent["workers"]), ("In Progress", ["ann.w1"]))
        self.say(f"2. kyle.r1's review-next claims TASK-1 ({review['kind']}; {review['model']}/{review['effort']}), in kyle's clone at "
                 f"{Path(str(review['repo'])).relative_to(self.root)}. It fetches {branch}, reads the diff against origin/{review['default_branch']} "
                 f"({len(diff.splitlines())} lines), and records changes: TASK-1 goes back In Progress for @ann.w1, labelled changes-requested.")

        # 3. Ann's orchestrator sees it come back, and her worker fixes it.
        back = ann.json("mine", "--as", "ann")
        self.assertEqual([r["id"] for r in back["changes_requested"]], ["TASK-1"])
        self.assertIn(findings, self.task(ann, "TASK-1"))
        self.build(ann, "TASK-1", worktree, "def login(user):\n    ok = check(user)\n    if not ok:\n        limit(user)\n    return ok\n", "Count failures only")
        self.submit(ann, "TASK-1", branch, 1, first=False)
        self.say("3. ann's `mine` lists TASK-1 under changes_requested. Her worker reads the findings on the task, fixes login.py, records the "
                 "check, pushes the same branch and sets it In Review again without the label.")

        # 4. Kyle's reviewer looks again and finds nothing.
        again = kyle.json("review-next", "--as", "kyle.r1")
        self.assertEqual(again["task"], "TASK-1")
        self.assertIn("+    if not ok:", self.diff(kyle, again))
        kyle.json("review-done", "TASK-1", "--as", "kyle.r1", "--verdict", "clean", "--notes", "No findings: failures only are counted.")
        final = self.task(kyle, "TASK-1")
        self.assertRegex(final, r"Status: \W*In Review")
        self.assertIn("review-passed", final)
        self.assertNotIn("changes-requested", final)
        self.assertIn("Review by @kyle.r1 (cross-machine): changes requested.", final)
        self.assertIn("Review by @kyle.r1 (cross-machine): clean.", final)
        self.say("4. kyle.r1 claims it again and marks it clean: TASK-1 stays In Review, labelled review-passed, with both reviews in its "
                 "comments, for a person to merge.")

        # 5. A task nobody else reviews: its author's machine takes it after the fallback.
        second = ann.json("next", "--as", "ann.w2")
        self.assertEqual(second["task"], "TASK-2")
        other = self.build(ann, "TASK-2", Path(str(second["worktree"])), "def login(user):\n    log(user)\n    return check(user)\n", "Log logins")
        self.submit(ann, "TASK-2", other, 2, first=True)
        now = datetime.now(UTC)
        early = ann.asdlc("review-next", "--as", "ann.r1", "--fallback", "--json", "--now", (now + timedelta(minutes=10)).isoformat())
        self.assertFalse(json.loads(early.stdout)["claimed"])
        self.assertIn("not yet longer than review_fallback_after (30m)", early.stderr)
        waited = early.stderr.split("it has waited ")[1].split(" for one")[0]
        late = ann.json("review-next", "--as", "ann.r1", "--fallback", "--now", (now + timedelta(minutes=35)).isoformat())
        self.assertEqual((late["task"], late["kind"], late["repo"]), ("TASK-2", "same-machine", str(self.api["ann"])))
        ann.json("review-done", "TASK-2", "--as", "ann.r1", "--verdict", "clean", "--notes", "No findings.")
        marked = self.task(kyle, "TASK-2")
        self.assertIn("same-machine review: it waited", marked)
        self.assertIn("Review by @ann.r1 (same-machine): clean.", marked)
        self.say("5. ann.w2 finishes TASK-2 and nobody else claims its review. At +10m ann's `review-next --fallback` still refuses "
                 "(waited " + waited + ", not yet longer than 30m); at +35m (`--now`) it claims TASK-2 as a same-machine review in ann's clone. "
                 "Her fresh reviewer marks it clean, and the task says it was a same-machine review for the person who merges it.")


if __name__ == "__main__":
    unittest.main()
