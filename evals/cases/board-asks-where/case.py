"""The board is wherever its user chooses: with no board anywhere the agent asks once, and builds nothing until it is told."""

import re
from pathlib import Path

import asdlc_eval as ev
import fixtures

QUESTION = re.compile(r"\?")
WHERE = re.compile(r"\b(where|which repo|this repo|repository|own repo|separate|dedicated)\b", re.I)
LINE = re.compile(r"(?i)\b(board|backlog)\b")


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, board=False)
    return world.facts(claude_before=(world.clone / "CLAUDE.md").read_text())


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    clone = Path(str(facts["app"]))
    if session == 0:
        script.skill("asdlc:capture-intent")
        script.bash("asdlc whoami", ok=False)
        return ("There's no board yet. Where should this work be kept: in this repository (a local board, committed to the branch you have checked "
                "out here), or in a repository of its own that others share?")
    script.bash("date -u +%Y-%m-%dT%H:%M:%SZ")
    script.bash("asdlc init-board --local .")
    script.bash("asdlc board task create 'Customers see only \"Login failed\"' --draft --type intent -d '## Problem\nCustomers who fail to log in only see \"Login failed\"; support wants to tell them why without revealing whether an account exists.' --ac 'A customer who is locked out is told so' --ac 'No message reveals whether an account exists'")
    claude = clone / "CLAUDE.md"
    script.write(claude, script.read(claude).rstrip("\n") + "\n\n## Work\n- The board lives in this repository (`backlog/`, local: `asdlc init-board --local .`); intents are drafts on it.\n")
    return "Made a local board in this repository and wrote the intent as a draft on it. I noted where the board lives in CLAUDE.md."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    tree = fixtures.tree(Path(str(facts["app"])))
    return {"CLAUDE.md": tree.get("CLAUDE.md", ""), "other_repos": "\n".join(fixtures.git_repos(fixture, Path(str(facts["app"])))),
            "has_board": str("backlog/config.yml" in tree)}


def _session(found: ev.Outcome, index: int) -> list[ev.Event]:
    return [e for e in found.events if e.session == index]


def asked_before_creating(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    first = _session(found, 0)
    built = [e.command for e in first if e.kind == "tool" and e.command and re.search(r"\binit-board\b|\bgit\s+init\b|backlog\s+init", e.command)]
    said = found.finals[0] if found.finals else ""
    if built:
        return False, f"built something before asking: {built[0][:120]}"
    if not (QUESTION.search(said) and WHERE.search(said)):
        return False, f"the first session ended without asking where the work should be kept: {said.strip()[:160]!r}"
    return True, "asked where before building anything"


def no_separate_tasks_repository(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    made = [c for c in ev.commands(found.events) if re.search(r"\binit-board\b", c) and "--local" not in c]
    others = [r for r in found.files.get("other_repos", "").splitlines() if r]
    if made or others:
        return False, f"created a repository of its own: {(made + others)[0][:160]}"
    return True, "no repository was created besides the one the work is in"


def intent_on_a_board_in_this_repository(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    intents = [i for i in found.clone_items().values() if i.type == "intent"]
    if found.files.get("has_board") != "True":
        return False, "there is no backlog/ in the repository"
    if not intents:
        return False, "the board is there but holds no intent"
    return True, f"{len(intents)} intent{'s' * (len(intents) != 1)} on the local board in this repository: {intents[0].title}"


def choice_recorded_in_claude_md(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    before, after = str(found.facts["claude_before"]), found.files.get("CLAUDE.md", "")
    added = [line for line in after.splitlines() if line not in before.splitlines() and line.strip()]
    if not any(LINE.search(line) for line in added):
        return False, "CLAUDE.md gained no line about where the board lives"
    if len(after.splitlines()) > 60:
        return False, f"CLAUDE.md is {len(after.splitlines())} lines, over the 60 it should stay within"
    return True, f"CLAUDE.md gained {len(added)} line{'s' * (len(added) != 1)} naming the board, and is {len(after.splitlines())} lines"


def no_push(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    updates = sum(len(repo.updates) for repo in found.code.values())
    return (False, f"{updates} pushes: a local board is never pushed by asdlc, and nobody asked for one") if updates else (True, "nothing was pushed")
