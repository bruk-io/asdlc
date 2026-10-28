"""With a board in the repository the agent uses it and does not ask where the work should be kept."""

import re
from pathlib import Path

import asdlc_eval as ev
import fixtures

CLAUDE = fixtures.SOLO_CLAUDE + "\n## Work\n- The board lives in this repository (`backlog/`, local); intents are drafts on it.\n"


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, board=True, claude_md=CLAUDE)
    return world.facts()


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    script.skill("asdlc:capture-intent")
    script.bash("asdlc whoami")
    script.bash("date -u +%Y-%m-%dT%H:%M:%SZ")
    script.bash("asdlc board task create 'Customers see only \"Login failed\"' --draft --type intent -d '## Problem\nCustomers who fail to log in only see \"Login failed\"; support wants to tell them why without revealing whether an account exists.' --ac 'A customer who is locked out is told so' --ac 'No message reveals whether an account exists'")
    return "Wrote the intent as a draft on this repository's board."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    return {"other_repos": "\n".join(fixtures.git_repos(fixture, Path(str(facts["app"]))))}


def did_not_ask_where(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    said = found.finals[0] if found.finals else ""
    asking = re.search(r"\b(where (should|do you want|would you like)|which (repo|repository|board))\b", said, re.I)
    if asking:
        return False, f"asked where the work should be kept although the repository has a board: {said.strip()[:160]!r}"
    return True, "did not ask where to keep the work"


def intent_on_the_existing_board(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    intents = [i for i in found.clone_items().values() if i.type == "intent"]
    return (True, f"intent {intents[0].id} written to the board that was already here: {intents[0].title}") if intents else (False, "no intent on the board")


def nothing_else_created(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    made = [c for c in ev.commands(found.events) if re.search(r"\binit-board\b|\bgit\s+init\b|backlog\s+init", c)]
    others = [r for r in found.files.get("other_repos", "").splitlines() if r]
    if made or others:
        return False, f"created a board or repository although one existed: {(made + others)[0][:160]}"
    return True, "no board or repository was created"
