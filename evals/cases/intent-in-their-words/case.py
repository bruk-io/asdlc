"""A request becomes a draft intent in the requester's own terms, with checkable outcomes."""

import re
import shlex
from pathlib import Path

import asdlc_eval as ev
import fixtures

PROBLEM = ('Customers who fail to log in only see "Login failed" and phone support; about a third of support\'s calls are that. Support wants '
           "customers told when the account is locked, but legal says we can never reveal whether an account exists.")
CRITERIA = ('A customer who is locked out is told their account is locked', 'No message, status or timing reveals whether an account exists',
            'Calls to support about "Login failed" fall')


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, board=True)
    return world.facts()


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    script.skill("asdlc:capture-intent")
    script.bash("asdlc whoami")
    script.bash("date -u +%Y-%m-%dT%H:%M:%SZ")
    acs = " ".join(f"--ac {shlex.quote(c)}" for c in CRITERIA)
    description = (f"Requested by @kyle.\n\n## Problem\n\n{PROBLEM}\n\n## Constraints\n\nLegal: we can never reveal whether an account exists.\n\n"
                   "## Open questions\n\n- [ ] How can a locked-out customer be told without revealing whether an account exists?")
    script.bash(f"asdlc board task create {shlex.quote('Customers see only \"Login failed\"')} --draft --type intent {acs} -d {shlex.quote(description)}")
    script.bash("asdlc board draft view DRAFT-1 --plain")
    return ("Here is the draft: DRAFT-1, Customers see only \"Login failed\". The problem is as you put it, the constraint is legal's, and the one open question "
            "is how to tell a locked-out customer without revealing whether an account exists. I guessed nothing; tell me what to correct.")


def _draft(found: ev.Outcome) -> ev.BoardItem | None:
    drafts = [i for i in found.clone_items().values() if i.type == "intent" and i.draft]
    return drafts[0] if drafts else None


def artefacts(found: ev.Outcome, case: ev.Case) -> dict[str, str]:
    """What the judges read: the request, and the draft."""
    draft = _draft(found)
    request = case.sessions[0].prompt
    text = draft.text if draft else ""
    return {"intent_faithful": f"REQUEST:\n{request}\n\nDRAFT INTENT:\n{text}", "intent_checkable": f"DRAFT INTENT:\n{text}"}


def intent_has_its_parts(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    draft = _draft(found)
    if draft is None:
        return False, "no draft intent on the board"
    missing = [h for h in ("Problem", "Constraints", "Open questions") if not re.search(rf"(?m)^##\s*{h}\b", draft.text)]
    return (False, f"{draft.id} is missing {', '.join(missing)}") if missing else (True, f"{draft.id} has Problem, Constraints and Open questions")


def outcomes_are_acceptance_criteria(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    draft = _draft(found)
    if draft is None:
        return False, "no draft intent on the board"
    criteria = re.findall(r"(?m)^- \[ \] #\d+ (.+)$", draft.section("AC") or draft.text)
    return (True, f"{len(criteria)} acceptance criteria") if criteria else (False, f"{draft.id} has no acceptance criteria")


def shown_to_the_person(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    said = found.finals[-1] if found.finals else ""
    if re.search(r"DRAFT-\d+", said) and re.search(r"(?i)\b(correct|change|tell me|guess|looks? right)\b", said):
        return True, "the final message names the draft and invites corrections"
    return False, f"the final message does not show the draft and ask for corrections: {said.strip()[:160]!r}"
