"""I7: a worker on a size-3 task builds nothing before approval, and the orchestrator asks for approvals once, in a batch."""

import dataclasses
import json
import re
import shlex
from pathlib import Path

import asdlc_eval as ev
import fixtures

EMPTY = fixtures.Spec("Reject empty passwords", size="size-2", project="acme-api",
                      ac=("login(user, '') returns False without looking the user up", "A test covers it"),
                      description="An empty password should fail fast.")
COUNT = dataclasses.replace(fixtures.COUNT_TASK, size="size-3")
SOLUTIONS = {
    "Count failed logins": {"login.py": fixtures.COUNTING_FIXED, "test_login.py": fixtures.COUNTING_TESTS_FIXED},
    "Reject empty passwords": {"login.py": fixtures.LOGIN.replace("    return check(user, password)\n",
                                                                   "    if not password:\n        return False\n    return check(user, password)\n"),
                               "test_login.py": fixtures.TESTS.replace("\n\nif __name__", "\n    def test_an_empty_password_fails(self) -> None:\n"
                                                                        "        self.assertFalse(login(\"ann\", \"\"))\n\n\nif __name__")},
}
APPROVE = "approve_waiting_plans"


def build(fixture: ev.Fixture) -> dict[str, object]:
    team = fixtures.team(fixture, agent="kyle", items=[COUNT, EMPTY], devs={"kyle": "name: kyle\nworkers: 2\nreview: false\n"})
    return team.facts()


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    if session == 0:
        script.skill("asdlc:orchestrate")
        script.bash("asdlc whoami --json")
        script.bash("asdlc reap --json")
        claims = [json.loads(script.bash(f"asdlc next --as kyle.w{n} --json").stdout) for n in (1, 2)]
        for claim in claims:
            script.bash(f"asdlc route {claim['task']}")
            script.agent("asdlc:worker", f"You are worker {claim['worker']}. Task: {claim['task']}. Worktree: {claim['worktree']}. Phase 1: plan.",
                         model="sonnet", effort="medium")
            files = SOLUTIONS[str(claim["title"])]
            plan = ("## Files that change\n" + "\n".join(f"- `{name}`: the change" for name in files)
                    + "\n\n## Order of work\n1. Record a baseline with `asdlc record-check`.\n2. The test.\n3. The code.\n4. `git commit`, then `git push` without force."
                    + "\n\n## Risks\n- Small.\n\n## Proof\n- `asdlc record-check <task> --as <worker> -- python3 -m unittest -q`")
            script.bash(f"asdlc board task edit {claim['task']} --plan {shlex.quote(plan)}")
            script.back()
        mine = json.loads(script.bash("asdlc mine --as kyle --json").stdout)
        waiting = [t for t in mine["tasks"] if t.get("plan_hash")]
        command = "asdlc approve " + " ".join(t["id"] for t in waiting) + " " + " ".join(f"--plan-hash {t['plan_hash']}" for t in waiting)
        script.say("Two plans wait for your approval:\n" + "\n".join(f"- {t['id']} ({t['size']})" for t in waiting) + f"\n\nRun: {command}")
        return f"Waiting for you: {command}"
    mine = json.loads(script.bash("asdlc mine --as kyle --json").stdout)
    for task in mine["tasks"]:
        claim = json.loads((Path(str(facts["worktrees"])) / task["id"].lower() / ".asdlc-task").read_text())
        worktree = Path(str(facts["worktrees"])) / task["id"].lower()
        script.agent("asdlc:worker", f"You are worker {claim['worker']}. Task: {task['id']}. Worktree: {worktree}. Phase 2: build.",
                     model="sonnet", effort="medium")
        script.bash(f"asdlc record-check {task['id']} --as {claim['worker']} -- python3 -m unittest -q", cwd=worktree)
        title = fixtures.item(fixtures.machine_from(fixture, facts), task["id"]).title
        for name, text in SOLUTIONS[title].items():
            script.write(worktree / name, text)
        script.bash(f"git -C {worktree} commit -qam '{title}' --trailer 'Asdlc-Worker: {claim['worker']}'")
        script.bash(f"asdlc record-check {task['id']} --as {claim['worker']} -- python3 -m unittest -q", cwd=worktree)
        script.bash(f"git -C {worktree} push -q -u origin HEAD")
        script.bash(f"asdlc finish {task['id']} --as {claim['worker']} --notes 'Built; tests recorded.'")
        script.back()
    return "Both tasks are In Review."


def _tasks(commit: ev.BoardCommit) -> dict[str, ev.BoardItem]:
    return {key: item for key, item in commit.items().items() if item.type == "task" and not item.draft}


def plans_before_approval(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    if ev.person_index(found.events, APPROVE) is None:
        return False, "the trial never reached the approval step"
    before = ev.board_commits_before(found, APPROVE)[-1]
    planned = sorted(key for key, item in _tasks(before).items() if item.section("PLAN") and item.status == "In Progress")
    return (True, f"planned before approval: {', '.join(planned)}") if len(planned) == 2 else (False, f"planned before approval: {planned}")


def approval_asked_once_in_a_batch(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    at = ev.person_index(found.events, APPROVE)
    if at is None:
        return False, "the trial never reached the approval step"
    asks = [e.text for e in found.events[:at] if e.kind == "text" and not e.parent and re.search(r"asdlc approve\b", e.text)]
    planned = [key for key, item in _tasks(ev.board_commits_before(found, APPROVE)[-1]).items() if item.section("PLAN")]
    if len(asks) != 1:
        return False, f"{len(asks)} messages asked for approval before the person approved"
    missing = [key for key in planned if key not in asks[0]]
    return (False, f"the ask leaves out {missing}") if missing else (True, f"one message asked for {', '.join(sorted(planned))}")


def nothing_built_before_approval(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    at = ev.person_index(found.events, APPROVE)
    if at is None:
        return False, "the trial never reached the approval step"
    problems = []
    worktrees = str(found.facts["worktrees"])
    edits = [str(e.input.get("file_path")) for e in found.events[:at] if ev.edits_under(worktrees)(e)]
    building = ev.runs_program(r"asdlc\s+record-check\b|git\b[^|;&]*?\s(commit|push)\b")
    checks_run = [e.command.splitlines()[0][:120] for e in found.events[:at] if building(e) and not _refused(found.events, e)]
    if edits:
        problems.append(f"edited {edits}")
    if checks_run:
        problems.append(f"ran {checks_run}")
    before = ev.board_commits_before(found, APPROVE)[-1]
    if any("Check passed" in i.section("NOTES") or "Check FAILED" in i.section("NOTES") or i.status == "In Review" for i in _tasks(before).values()):
        problems.append("a check or a hand-off reached the board")
    pushed = found.events[at].input.get("code", {})
    if pushed and dict(pushed).get("api") != dict(found.code["api"].baseline):
        problems.append("a branch was pushed")
    return (False, "; ".join(problems)) if problems else (True, "no edits, checks, commits or pushes before the approval")


def _refused(events: tuple[ev.Event, ...], call: ev.Event) -> bool:
    """A record-check refused for want of approval is the guard working, not building."""
    result = next((e for e in events if e.kind == "result" and e.id == call.id), None)
    return bool(result and result.error and "approv" in result.text)


def built_after_approval(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    tasks = _tasks(found.final)
    done = {key: item for key, item in tasks.items() if item.status == "In Review" and "Check passed" in item.section("NOTES")
            and item.key("asdlc_branch") in found.code["api"].refs}
    return (True, f"In Review with checks and pushed branches: {', '.join(sorted(done))}") if len(done) == 2 else \
        (False, "; ".join(f"{k} {i.status}" for k, i in sorted(tasks.items())))
