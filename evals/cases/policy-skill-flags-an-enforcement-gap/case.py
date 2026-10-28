"""A policy that must always hold but is enforced by nothing: the skill says advisory only, and the person is told."""

import re
from pathlib import Path

import asdlc_eval as ev
import fixtures

SKILL = """---
name: no-request-bodies-in-logs
description: Apply the logging standard when adding logging to an endpoint or reviewing API code.
---

# No request bodies in logs

- Owner: Aisha Khan (security)
- Source: https://wiki.example.com/logging
- Enforced by: advisory only

Bodies can hold personal data, so they never reach a log.

## The policy

1. No endpoint logs a request body.

## Checking it

Read the diff for log calls that include a request or response body.
"""


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, files={"endpoints.py": fixtures.ENDPOINTS})
    return world.facts(owner="Aisha Khan", source="https://wiki.example.com/logging")


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    clone = Path(str(facts["app"]))
    script.skill("asdlc:write-policy-skill")
    script.write(clone / ".claude" / "skills" / "no-request-bodies-in-logs" / "SKILL.md", SKILL)
    return ("Wrote .claude/skills/no-request-bodies-in-logs/SKILL.md. It is advisory only: nothing enforces this policy yet, so a session can still log "
            "a body. A hook or a check on pull requests is a piece of work of its own; tell Aisha it is missing.")


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    return fixtures.policy_files(Path(str(facts["app"])))


def enforced_by_says_advisory(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    enforced = re.search(r"(?im)^\W*enforced by\W*:?\s*(.+)$", found.files.get("skill", ""))
    if enforced and re.search(r"advisory|none|nothing|not enforced", enforced.group(1), re.I):
        return True, f"Enforced by: {enforced.group(1).strip()[:80]}"
    return False, f"Enforced by claims something that does not exist, or is missing: {enforced.group(1)[:120] if enforced else 'no such line'}"


def tells_the_person_about_the_gap(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    said = found.finals[-1] if found.finals else ""
    if re.search(r"(nothing|no (hook|check|script)|not) (enforces?|enforced|backs?|yet)|advisory", said, re.I):
        return True, "the final message says nothing enforces the policy"
    return False, f"the final message does not say the policy is unenforced: {said.strip()[:160]!r}"
