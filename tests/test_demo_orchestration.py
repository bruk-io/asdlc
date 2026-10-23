"""A scripted demonstration of orchestration across two machines, with no model calls.

Two engineers, kyle and ann, each on their own machine: their own git identity and
`asdlc.engineer` (a global git config file each), their own registry of code repositories
(`XDG_CONFIG_HOME` each), their own clone of the board and their own clones of the two
code repositories. One intent with four children across the two repositories, one child
reserved for ann. It shows the lead claim, reserved work, preferences, workers spreading
over the work, and a stale claim reaped after the clock jumps.

Run it with ASDLC_DEMO=1 to print the story; the pull request quotes that output.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.support import ROOT, run_script
from tests.test_asdlc import BACKLOG, asdlc, needs_backlog

SAY = bool(os.environ.get("ASDLC_DEMO"))


class Machine:
    """One engineer's computer: their git config, their registry, their clones."""

    def __init__(self, root: Path, name: str, board_origin: Path) -> None:
        self.name = name
        self.home = root / name
        self.home.mkdir()
        gitconfig = self.home / ".gitconfig"
        gitconfig.write_text(
            f"[asdlc]\n\tengineer = {name}\n[user]\n\tname = {name.title()}\n\temail = {name}@example.com\n"
            "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n"
        )
        self.env = {"GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": str(self.home / "config"),
                    "XDG_STATE_HOME": str(self.home / "state"),
                    "ASDLC_BACKLOG": BACKLOG or "backlog"}
        self.board = self.home / "board"
        self.git(root, "clone", "--quiet", str(board_origin), str(self.board))

    def git(self, where: Path, *args: str, env: dict[str, str] | None = None) -> str:
        done = subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True, env={**os.environ, **self.env, **(env or {})})
        if done.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
        return done.stdout.strip()

    def asdlc(self, *args: str, cwd: Path | None = None, env: dict[str, str] | None = None, ok: bool = True) -> subprocess.CompletedProcess[str]:
        done = run_script("scripts/asdlc", *args, cwd=cwd or self.board, env={**self.env, **(env or {})})
        if ok and done.returncode != 0:
            raise AssertionError(f"{self.name}: asdlc {' '.join(args)} failed: {done.stderr}")
        return done

    def json(self, *args: str, **options: object) -> dict[str, object]:
        return json.loads(self.asdlc(*args, "--json", **options).stdout)

    def clone_code(self, origin: Path, name: str) -> Path:
        path = self.home / name
        self.git(self.home, "clone", "--quiet", str(origin), str(path))
        self.asdlc("register", "--board", str(self.board), cwd=path)
        return path


@needs_backlog
class TwoMachinesTest(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.root = Path(handle.name).resolve()
        self.story: list[str] = []
        board_origin = self._origins()
        self.kyle = Machine(self.root, "kyle", board_origin)
        self.ann = Machine(self.root, "ann", board_origin)
        origins = self.root / "origins" / "acme"
        for machine in (self.kyle, self.ann):
            machine.clone_code(origins / "api.git", "api")
            machine.clone_code(origins / "web.git", "web")

    def _origins(self) -> Path:
        """A bare board repository (made by asdlc init-board) and two bare code repositories."""
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
        (seed / "devs" / "kyle.yaml").write_text("name: kyle\nprefer: [acme-web]\nworkers: 3\n")
        (seed / "devs" / "ann.yaml").write_text("name: ann\nprefer: [acme-api]\nworkers: 3\n")
        (seed / "asdlc.toml").write_text('stale_after = "2h"\n')
        git("-C", str(seed), "add", "devs", "asdlc.toml")
        git("-C", str(seed), "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "-m", "Preferences and settings")
        git("-C", str(seed), "remote", "add", "origin", str(board))
        git("-C", str(seed), "push", "--quiet", "origin", "main")
        for name in ("api", "web"):
            origin = self.root / "origins" / "acme" / f"{name}.git"
            git("init", "--quiet", "--bare", "-b", "main", str(origin))
            work = self.root / f"seed-{name}"
            git("clone", "--quiet", str(origin), str(work))
            (work / "README.md").write_text(f"{name}\n")
            git("-C", str(work), "add", ".")
            git("-C", str(work), "commit", "--quiet", "-m", "start")
            git("-C", str(work), "push", "--quiet", "origin", "main")
        return board

    def say(self, line: str) -> None:
        self.story.append(line)

    def tearDown(self) -> None:
        if SAY:
            print("\n" + "\n".join(self.story), flush=True)

    def test_two_engineers_two_machines(self) -> None:
        kyle, ann = self.kyle, self.ann
        self.say("Two machines: kyle and ann, each with a board clone and clones of acme/api and acme/web, registered.")

        # 1. The intent and its lead.
        created = kyle.asdlc("board", "task", "create", "Checkout v2", "--draft", "--type", "intent", "--ac", "A buyer can pay in one step")
        self.assertIn("DRAFT-1", created.stdout)
        led = kyle.json("lead", "DRAFT-1", "--as", "kyle.lead")
        self.assertTrue(led["mine"])
        seen = ann.json("lead-of", "DRAFT-1")
        self.assertEqual(seen["lead"], "kyle.lead")
        second = ann.asdlc("lead", "DRAFT-1", "--as", "ann.lead", "--json", ok=False)
        self.assertEqual((second.returncode, json.loads(second.stdout)["lead"]), (1, "kyle.lead"))
        self.say("1. kyle's orchestrator claims the lead on DRAFT-1. ann's sees it: "
                 f"`lead-of` says @{seen['lead']}, and `lead --as ann.lead` exits 1 ({json.loads(second.stdout)['reason'].split('. Work')[0]}).")

        # 2. The lead's breakdown: four child drafts across two repositories, one reserved for ann.
        children = (
            ("Payment API", "acme-api", "size-2", ()),
            ("Order API", "acme-api", "size-2", ()),
            ("Checkout page", "acme-web", "size-2", ("--priority", "low")),
            ("Saved cards UI", "acme-web", "size-1", ("-a", "@ann")),
        )
        for title, project, size, extra in children:
            kyle.asdlc("board", "task", "create", title, "--draft", "-p", "DRAFT-1", "--project", project, "-l", size, "--priority", "medium", *extra)
        accepted = kyle.json("accept", "DRAFT-1")
        self.assertEqual(accepted["accepted"], {"DRAFT-1": "TASK-1", "DRAFT-2": "TASK-1.1", "DRAFT-3": "TASK-1.2", "DRAFT-4": "TASK-1.3", "DRAFT-5": "TASK-1.4"})
        self.say("2. The lead drafts four children under DRAFT-1 (two in acme-api, two in acme-web; 'Saved cards UI' "
                 "reserved for @ann). kyle, the person, runs `asdlc accept DRAFT-1`: one commit makes "
                 + ", ".join(f"{a}->{b}" for a, b in accepted["accepted"].items()) + ".")
        self.assertEqual(ann.json("lead-of", "TASK-1.2")["lead"], "kyle.lead")

        # 3. Reserved work only goes to its owner.
        refused = kyle.asdlc("claim", "TASK-1.4", "--as", "kyle.w9", ok=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("reserved for @ann", refused.stderr)
        ann_first = ann.json("next", "--as", "ann.w1")
        self.assertEqual(ann_first["task"], "TASK-1.4")
        self.say(f"3. kyle.w9 claiming TASK-1.4 is refused ('reserved for @ann'). ann.w1's `next` takes it first: {ann_first['task']}, "
                 f"assignees @ann and @ann.w1, worktree {Path(str(ann_first['worktree'])).relative_to(self.root)}.")

        # 4. Preferences change the pick order.
        kyle.git(kyle.board, "pull", "--quiet", "--rebase", "origin", "main")
        board = [t for p in sorted((kyle.board / "backlog" / "tasks").glob("*.md")) if (t := asdlc.task_from(p.name, p.read_text()))]
        registered = frozenset({"acme-api", "acme-web"})
        without = asdlc.candidates(board, asdlc.Picker("kyle", "kyle.w1", registered))[0]
        self.assertEqual(without[0].project, "acme-api")
        kyle_first = kyle.json("next", "--as", "kyle.w1")
        self.assertEqual(kyle_first["task"], "TASK-1.3")
        self.say(f"4. kyle prefers acme-web, so kyle.w1 takes {kyle_first['task']} (Checkout page, priority low) over the "
                 "medium-priority acme-api tasks it would otherwise have taken first.")

        # 5. Workers spread over the best tier instead of racing for one task.
        racers = [
            subprocess.Popen([sys.executable, str(ROOT / "scripts" / "asdlc"), "next", "--as", worker, "--json"], cwd=ann.board,
                             env={**os.environ, **ann.env}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for worker in ("ann.w2", "ann.w3")
        ]
        results = [(r.wait(timeout=120), *r.communicate()) for r in racers]
        picked = {json.loads(out)["worker"]: json.loads(out)["task"] for code, out, _ in results if code == 0}
        self.assertEqual(picked, {"ann.w2": "TASK-1.2", "ann.w3": "TASK-1.1"})
        self.assertFalse(any("first" in err for _, _, err in results), "a spread worker lost a race")
        self.say(f"5. ann.w2 and ann.w3 run `next` at once. ann prefers acme-api, whose two tasks tie; w2 starts second and w3 "
                 f"wraps to first, so they take {picked['ann.w2']} and {picked['ann.w3']} with no lost race.")

        mine = kyle.json("mine", "--as", "ann")
        self.assertEqual(sorted(t["id"] for t in mine["tasks"]), ["TASK-1.1", "TASK-1.2", "TASK-1.4"])

        # 6. ann's machine goes quiet; kyle's keeps heartbeating; the clock jumps three hours.
        jump = datetime.now(UTC) + timedelta(hours=3)
        beating = {"GIT_COMMITTER_DATE": (jump - timedelta(minutes=10)).isoformat()}
        kyle.asdlc("heartbeat", "TASK-1.3", "--as", "kyle.w1", env=beating)
        kyle.asdlc("heartbeat", "TASK-1", "--as", "kyle.lead", env=beating)
        reaped = kyle.json("reap", "--now", jump.isoformat())
        released = sorted((r["id"], r["holders"][0]) for r in reaped["released"])
        self.assertEqual(released, [("TASK-1.1", "ann.w3"), ("TASK-1.2", "ann.w2"), ("TASK-1.4", "ann.w1")])
        after = {t["id"]: t for t in kyle.json("mine", "--as", "ann")["reserved"]}
        self.assertIn("TASK-1.4", after)
        self.assertEqual([t["id"] for t in kyle.json("mine", "--as", "kyle")["tasks"]], ["TASK-1.3"])
        self.say("6. ann's machine goes quiet. kyle's keeps heartbeating TASK-1.3 and the lead on TASK-1. The clock jumps 3h "
                 "(`reap --now`); kyle's orchestrator releases " + ", ".join(f"{i} (@{h})" for i, h in released)
                 + ". TASK-1.4 goes back to To Do still reserved for @ann; kyle.w1's task and kyle's lead stay.")

        again = kyle.json("next", "--as", "kyle.w2")
        self.assertIn(again["task"], ("TASK-1.1", "TASK-1.2"))
        self.say(f"7. kyle.w2 then picks up released work in acme-api ({again['task']}); TASK-1.4 stays for ann.")


if __name__ == "__main__":
    unittest.main()
