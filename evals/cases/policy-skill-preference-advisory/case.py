"""A preference is a skill and nothing more: no hook, script, setting or workflow, and no alarm about enforcement."""

import re
from pathlib import Path

import asdlc_eval as ev
import fixtures

SKILL = """---
name: docstring-style
description: Apply the docstring style when writing or changing a function's docstring, or reviewing docstrings.
---

# Docstring style

- Owner: Priya Raman (the tech lead)
- Source: https://wiki.example.com/style
- Enforced by: advisory only

A one-line summary lets a reader scan a module without reading each function.

## The policy

1. Start every docstring with a one-line summary in the imperative mood.

## Checking it

Read the docstrings the change adds or edits.
"""


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture)
    return world.facts(owner="Priya Raman", source="https://wiki.example.com/style")


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    clone = Path(str(facts["app"]))
    script.skill("asdlc:write-policy-skill")
    script.write(clone / ".claude" / "skills" / "docstring-style" / "SKILL.md", SKILL)
    return "Wrote .claude/skills/docstring-style/SKILL.md, advisory only, with Priya as owner and the wiki page as source."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    return fixtures.policy_files(Path(str(facts["app"])))


def advisory_and_nothing_built(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    enforced = re.search(r"(?im)^\W*enforced by\W*:?\s*(.+)$", found.files.get("skill", ""))
    built = [name for name in ("hook_scripts", "new_scripts", "settings", "workflows") if found.files.get(name, "").strip()]
    if built:
        return False, f"built enforcement for a preference: {', '.join(built)}"
    if not enforced or not re.search(r"advisory|none|nothing", enforced.group(1), re.I):
        return False, f"Enforced by does not say advisory only: {enforced.group(1)[:120] if enforced else 'no such line'}"
    return True, "advisory only, and nothing built behind it"


def gap_not_raised_as_a_problem(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    said = found.finals[-1] if found.finals else ""
    if re.search(r"(?i)\b(gap|nothing enforces|should (add|build) a (hook|check)|needs? (a )?(hook|check))\b", said):
        return False, f"the final message treats a preference's lack of enforcement as a problem: {said.strip()[:160]!r}"
    return True, "no enforcement gap was raised for a preference"
