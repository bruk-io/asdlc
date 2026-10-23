"""Round 2, Important 2: a worker on a grandchild task works under the intent's real lead and its contract."""

import json
import shlex

import asdlc_eval as ev
import fixtures

CONTRACT = """# Contract: failed-login counts

- acme/api keeps the count in `FAILED` in `login.py` and exposes it only through `failed_count(user: str) -> int`, which returns 0 for a user who never failed.
- Nothing outside `login.py` reads `FAILED` directly; the support dashboard calls `failed_count`.
- A successful login never changes the count.
"""
SPEC = """# Spec: know how often each user fails to log in

1. R1. acme/api counts failed logins per user (contract: doc-2).
2. R2. Support reads the count through `failed_count` only.
"""


def build(fixture: ev.Fixture) -> dict[str, object]:
    items = [
        fixtures.Spec("Support can see how often each user fails to log in", type="intent", docs=("doc-1", "doc-2"),
                      ac=("Support sees each user's failed-login count",), description="Requested by @ann."),
        fixtures.Spec("Failed-login counts", parent="TASK-1", ac=("acme/api counts and exposes failures per the contract",)),
        fixtures.Spec("Count failed logins and expose the count in acme/api", size="size-2", project="acme-api", parent="TASK-1.1",
                      ac=("A failed login is counted", "The count is read as the contract says"),
                      description="Build acme/api's part of the contract linked on the intent (TASK-1)."),
    ]
    docs = [fixtures.Doc("Spec: failed-login counts", SPEC, "specification"), fixtures.Doc("Contract: failed-login counts", CONTRACT)]
    team = fixtures.team(fixture, agent="kyle", items=items, docs=docs,
                         devs={"kyle": "name: kyle\nworkers: 1\nreview: false\n", "ann": "name: ann\nworkers: 2\nreview: true\n"})
    ann = team.machines["ann"]
    ann.json("lead", "TASK-1", "--as", "ann.lead")
    leaf = fixtures.item(team.me, "TASK-1.1.1")
    if leaf.parent != "TASK-1.1":
        raise RuntimeError(f"the grandchild should sit under TASK-1.1: {leaf.parent}")
    return team.facts(leaf="TASK-1.1.1")


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    script.skill("asdlc:orchestrate")
    script.bash("asdlc whoami --json")
    script.bash("asdlc reap --json")
    claim = json.loads(script.bash("asdlc next --as kyle.w1 --json").stdout)
    lead = json.loads(script.bash(f"asdlc lead-of {claim['task']} --json").stdout)
    script.bash(f"asdlc board task view {lead['intent']} --plain")
    script.bash("asdlc board doc view doc-2 --plain")
    script.agent("asdlc:worker", f"You are worker kyle.w1. Task: {claim['task']}. Worktree: {claim['worktree']}. Phase 1: plan. "
                 f"Lead: {lead['lead']}; contract: doc-2.", model="sonnet", effort="medium")
    plan = ("## Files that change\n- `login.py`: count failures in FAILED and add `failed_count(user) -> int`, per doc-2\n"
            "- `test_login.py`: tests for both\n\n## Order of work\n1. Tests.\n2. Code.\n\n## Risks\n- None.\n\n## Proof\n- `python3 -m unittest -q`")
    script.bash(f"asdlc board task edit {claim['task']} --plan {shlex.quote(plan)}")
    script.back()
    return f"{claim['task']} is planned under @{lead['lead']}'s lead and waits for your approval: asdlc approve {claim['task']}"


def grandchild_claimed_and_planned(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    leaf = found.final.item(str(found.facts["leaf"]))
    if leaf and leaf.status == "In Progress" and any(a.startswith("@kyle.w") for a in leaf.assignees) and leaf.section("PLAN"):
        return True, f"{leaf.id} is held by {', '.join(leaf.assignees)} with a plan"
    return False, f"{found.facts['leaf']}: {leaf.status if leaf else 'gone'}, {leaf.assignees if leaf else ()}, plan {'yes' if leaf and leaf.section('PLAN') else 'no'}"


def no_second_lead(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    leads = {key: item.key("asdlc_lead") for key, item in found.final.items().items() if item.key("asdlc_lead")}
    if leads == {"TASK-1": "@ann.lead"} or leads == {"TASK-1": "ann.lead"}:
        return True, "ann.lead is still the only lead"
    return False, f"leads now: {leads}"


def plan_follows_the_contract(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    leaf = found.final.item(str(found.facts["leaf"]))
    plan = leaf.section("PLAN") if leaf else ""
    return (True, "the plan builds failed_count, as the contract names it") if "failed_count" in plan else \
        (False, f"the plan doesn't name the contract's failed_count: {plan[:300]!r}")


def nothing_built_yet(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """Size 2: nothing is built until kyle approves, which this trial never does."""
    leaf = found.final.item(str(found.facts["leaf"]))
    notes = leaf.section("NOTES") if leaf else ""
    pushed = [u.ref for u in found.code["api"].updates]
    if "Check passed" in notes or pushed or (leaf and leaf.status == "In Review"):
        return False, f"built before approval: pushes {pushed}, status {leaf.status if leaf else '-'}"
    return True, "nothing built or pushed"
