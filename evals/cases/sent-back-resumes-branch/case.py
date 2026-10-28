"""B2: a changes-requested task picked up again resumes its branch: the pull request's commits survive, no force push.

The scene is a worker that finished and a worktree that is gone, not a reaped claim: it is the same bug, a rebuild from
main over the pushed branch, and it does not depend on more than one machine."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import asdlc_eval as ev
import fixtures

FINDINGS = ("[Bugs, Important] login.py:12 login() adds to FAILED before check(), so successful logins are counted too; "
            "count only failures, and add a test that a successful login leaves FAILED alone.")
README = "# acme/api\n\nLogins for acme.\n"
BEHAVIOUR = """
from login import FAILED, login
login("ann", "s3cret")
assert "ann" not in FAILED or FAILED["ann"] == 0, f"a successful login was counted: {FAILED}"
login("ann", "nope")
assert FAILED.get("ann") == 1, f"a failed login wasn't counted once: {FAILED}"
print("ok")
"""


def build(fixture: ev.Fixture) -> dict[str, object]:
    team = fixtures.team(fixture, agent="kyle", items=[fixtures.COUNT_TASK],
                         devs={"kyle": "name: kyle\nworkers: 2\nreview: true\n", "ann": "name: ann\nworkers: 2\nreview: true\n"})
    kyle, ann = team.me, team.machines["ann"]
    claimed = fixtures.claim(kyle, "TASK-1", "kyle.w1")
    first = Path(str(claimed["worktree"]))
    fixtures.plan_and_approve(kyle, "TASK-1")
    shas = fixtures.build_round(kyle, "TASK-1", "kyle.w1", first, [("Count failed logins", {"login.py": fixtures.COUNTING}),
                                                                   ("Test the count", {"test_login.py": fixtures.COUNTING_TESTS})],
                                "https://github.com/acme/api/pull/3")
    review = ann.json("review-next", "--as", "ann.r1")
    ann.json("review-done", "TASK-1", "--as", "ann.r1", "--verdict", "changes", "--findings", "important=1,nit=0", "--policy", "review",
             "--plan-matched", "yes", "--notes", FINDINGS)
    # Someone else's change lands on main meanwhile.
    work = ann.clones["api"]
    (work / "README.md").write_text(README)
    ann.git(work, "add", "README.md")
    ann.git(work, "commit", "--quiet", "-m", "Say what acme/api is")
    ann.git(work, "push", "--quiet", "origin", "HEAD:main")
    # kyle.w1 is done with the task and its worktree is gone from kyle's machine.
    kyle.asdlc("release", "TASK-1", "--as", "kyle.w1")
    kyle.git(kyle.clones["api"], "worktree", "remove", "--force", str(first))
    kyle.git(kyle.clones["api"], "branch", "-D", str(claimed["branch"]))
    again = kyle.json("next", "--as", "kyle.w2")
    if again.get("task") != "TASK-1" or not again.get("resumed_from"):
        raise RuntimeError(f"kyle.w2 should have resumed TASK-1 from its pushed branch: {again}")
    return team.facts(worktree=again["worktree"], branch=again["branch"], original=shas, findings=FINDINGS, review=review["task"])


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    worktree = Path(str(facts["worktree"]))
    script.bash("asdlc board task view TASK-1 --plain")
    script.write(worktree / "login.py", fixtures.COUNTING_FIXED)
    script.write(worktree / "test_login.py", fixtures.COUNTING_TESTS_FIXED)
    script.bash(f"git -C {worktree} commit -qam 'Count only failed logins' --trailer 'Asdlc-Worker: kyle.w2'")
    script.bash(f"git -C {worktree} fetch origin")
    script.bash(f"git -C {worktree} merge --no-edit origin/main")
    script.bash("asdlc record-check TASK-1 --as kyle.w2 -- python3 -m unittest -q", cwd=worktree)
    script.bash(f"git -C {worktree} push origin HEAD")
    script.bash("asdlc finish TASK-1 --as kyle.w2 --notes 'Counted only failures, as the review asked; added a test for a successful login.'")
    return "Fixed the finding, merged main, pushed the same branch, and handed TASK-1 back to review."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    """Run the behaviour the finding asked for against the branch's tip on origin, on the host."""
    origin, branch = Path(str(facts["code_origins"]["api"])), str(facts["branch"])
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, **ev.SEED_ENV}
        subprocess.run(["git", "clone", "--quiet", "--branch", branch, str(origin), scratch], capture_output=True, env=env, check=True)
        done = subprocess.run([sys.executable, "-c", BEHAVIOUR], cwd=scratch, capture_output=True, text=True)
    return {"behaviour": done.stdout.strip() if done.returncode == 0 else (done.stderr.strip().splitlines() or ["failed"])[-1]}


def original_commits_survive(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    branch = str(found.facts["branch"])
    tip = found.code["api"].commits.get(branch, ())
    lost = [sha[:8] for sha in found.facts["original"] if sha not in tip]
    if lost:
        return False, f"commits gone from {branch}: {', '.join(lost)}"
    return True, f"both of the pull request's commits are still on {branch} ({len(tip)} commits)"


def handed_back_for_review(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    task = found.final.item("TASK-1")
    if task and task.status == "In Review" and "changes-requested" not in task.labels and "@kyle.w2" in task.assignees:
        return True, "In Review again, without changes-requested, held by kyle.w2"
    return False, f"TASK-1 is {task.status if task else 'gone'} with labels {task.labels if task else ()}"


def finding_fixed(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    said = found.files.get("behaviour", "")
    return (True, "only failed logins are counted on the pushed branch") if said == "ok" else (False, f"on the pushed branch: {said}")
