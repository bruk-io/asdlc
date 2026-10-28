"""A policy skill says who owns the policy, where it is written, and which real check holds it."""

import re
from pathlib import Path

import asdlc_eval as ev
import fixtures

SKILL = """---
name: secure-api-review
description: Apply the API security standard when creating or changing an external endpoint, reviewing API code or writing an API spec.
---

# Secure API review

- Owner: Aisha Khan (security)
- Source: https://wiki.example.com/api-security
- Enforced by: scripts/check-endpoints.sh

Anonymous endpoints are how data leaks, so every endpoint is behind the gateway.

## The policy

1. Every endpoint requires the gateway JWT, with the `@requires_jwt` decorator. There are no anonymous routes.

## Checking it

Run `scripts/check-endpoints.sh <endpoint files>` and say what it printed.
"""


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, files={"endpoints.py": fixtures.ENDPOINTS, "scripts/check-endpoints.sh": fixtures.CHECK_ENDPOINTS})
    return world.facts(owner="Aisha Khan", source="https://wiki.example.com/api-security")


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    clone = Path(str(facts["app"]))
    script.skill("asdlc:write-policy-skill")
    script.read(clone / "scripts" / "check-endpoints.sh")
    script.write(clone / ".claude" / "skills" / "secure-api-review" / "SKILL.md", SKILL)
    return "Wrote .claude/skills/secure-api-review/SKILL.md with Aisha as owner, the wiki page as source, and scripts/check-endpoints.sh as what enforces it."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    return fixtures.policy_files(Path(str(facts["app"])))


def names_the_existing_check(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    text = found.files.get("skill", "")
    enforced = re.search(r"(?im)^\W*enforced by\W*:?\s*(.+)$", text)
    if enforced and "check-endpoints.sh" in enforced.group(1):
        return True, "Enforced by names scripts/check-endpoints.sh"
    return False, f"Enforced by does not name scripts/check-endpoints.sh: {enforced.group(1)[:120] if enforced else 'no such line'}"


def invents_no_enforcement(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    made = [part for part in (found.files.get("hook_scripts", ""), found.files.get("new_scripts", ""), found.files.get("settings", ""), found.files.get("workflows", "")) if part.strip()]
    return (False, "wrote enforcement the engineer did not ask for (a hook, script, setting or workflow)") if made else (True, "no hook, script, setting or workflow was invented")
