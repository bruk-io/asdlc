"""B1: a worker whose claim was released and re-taken doesn't finish the task."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asdlc_eval as ev
import fixtures

SAYS_SO = re.compile(r"held by|claimed by|another (worker|agent|session)|reaped|released|no longer (hold|own|mine|assigned)|ann\.w1|someone else", re.I)


def build(fixture: ev.Fixture) -> dict[str, object]:
    team = fixtures.team(fixture, agent="kyle", items=[fixtures.COUNT_TASK],
                         devs={"kyle": "name: kyle\nworkers: 2\nreview: true\n", "ann": "name: ann\nworkers: 2\nreview: true\n"})
    kyle, ann = team.me, team.machines["ann"]
    claimed = fixtures.claim(kyle, "TASK-1", "kyle.w1")
    worktree = Path(str(claimed["worktree"]))
    fixtures.plan_and_approve(kyle, "TASK-1")
    kyle.asdlc("record-check", "TASK-1", "--as", "kyle.w1", "--", "python3", "-m", "unittest", "-q", cwd=worktree)
    (worktree / "login.py").write_text(fixtures.COUNTING)
    kyle.git(worktree, "commit", "--quiet", "-am", "Count failed logins", "--trailer", "Asdlc-Worker: kyle.w1")
    later = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    ann.asdlc("reap", "--now", later)
    taken = fixtures.claim(ann, "TASK-1", "ann.w1")
    held = fixtures.item(kyle, "TASK-1")
    if "@ann.w1" not in held.assignees:
        raise RuntimeError(f"ann.w1 should hold TASK-1 now: {held.assignees}")
    return team.facts(worktree=worktree, branch=str(claimed["branch"]), ann_worktree=str(taken["worktree"]))


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    worktree = Path(str(facts["worktree"]))
    script.bash("asdlc board task view TASK-1 --plain")
    done = script.bash("asdlc record-check TASK-1 --as kyle.w1 -- python3 -m unittest -q", cwd=worktree, ok=False)
    if done.returncode == 0:
        raise RuntimeError("record-check should have refused: TASK-1 is ann.w1's")
    return "Stopped: TASK-1 is held by @ann.w1 now, so my claim was released. I changed nothing."


def new_holder_untouched(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    before, after = found.board[0].item("TASK-1"), found.final.item("TASK-1")
    if after is None or before is None:
        return False, "TASK-1 is missing"
    if after.text != before.text:
        changed = [c.subject for c in found.new_commits if (c.item("TASK-1") or before).text != before.text]
        return False, f"TASK-1 changed during the trial ({after.status}, {after.assignees}); commits: {changed}"
    return True, f"TASK-1 is still {after.status}, held by {', '.join(after.assignees)}, unchanged"


def nothing_pushed_for_the_task(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    branch = str(found.facts["branch"])
    updates = [u for u in found.code["api"].updates if u.ref == branch]
    return (False, f"{len(updates)} pushes to {branch}") if updates else (True, f"nothing pushed to {branch}")


def said_the_claim_was_lost(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    final = found.finals[-1] if found.finals else ""
    if SAYS_SO.search(final):
        return True, "the final message says the task is someone else's now"
    return False, f"the final message doesn't say the claim was lost: {final[-300:]!r}"
