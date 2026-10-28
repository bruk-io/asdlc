"""A policy that must hold is backed twice: a hook at the edit, and the same check on the pull request."""

import json
import re
from pathlib import Path

import asdlc_eval as ev
import fixtures

SKILL = """---
name: secure-api-review
description: Apply the API security standard when creating or changing an external endpoint or reviewing API code.
---

# Secure API review

- Owner: Aisha Khan (security)
- Source: https://wiki.example.com/api-security
- Enforced by: a hook that runs scripts/check-endpoints.sh after each edit, and the same script as a required pull request check

## The policy

1. Every endpoint requires the gateway JWT, with the `@requires_jwt` decorator.

## Checking it

Run `scripts/check-endpoints.sh <endpoint files>`.
"""
HOOK = """#!/bin/sh
# Backs the secure-api-review skill with the script it names.
file=$(jq -r '.tool_input.file_path')
case "$file" in
  */endpoints.py) ;;
  *) exit 0 ;;
esac
if ! out=$("$CLAUDE_PROJECT_DIR/scripts/check-endpoints.sh" "$file" 2>&1); then
  echo "secure-api-review: $out" >&2
  exit 2
fi
"""
SETTINGS = {"hooks": {"PostToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/api-policy.sh"}]}]}}
WORKFLOW = """name: API policy
on: pull_request
jobs:
  check-endpoints:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: scripts/check-endpoints.sh endpoints.py
"""


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, files={"endpoints.py": fixtures.ENDPOINTS, "scripts/check-endpoints.sh": fixtures.CHECK_ENDPOINTS})
    return world.facts(owner="Aisha Khan", source="https://wiki.example.com/api-security")


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    clone = Path(str(facts["app"]))
    script.skill("asdlc:write-policy-skill")
    script.write(clone / ".claude" / "skills" / "secure-api-review" / "SKILL.md", SKILL)
    script.write(clone / ".claude" / "hooks" / "api-policy.sh", HOOK)
    script.write(clone / ".claude" / "settings.json", json.dumps(SETTINGS, indent=2) + "\n")
    script.write(clone / ".github" / "workflows" / "api-policy.yml", WORKFLOW)
    return "Wrote the skill, a PostToolUse hook that runs scripts/check-endpoints.sh after edits and blocks, and the same script as a pull request check."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    return fixtures.policy_files(Path(str(facts["app"])))


def hook_runs_the_script_and_blocks(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    try:
        settings = json.loads(found.files.get("settings", "") or "{}")
    except ValueError:
        return False, ".claude/settings.json is not JSON"
    hooks = [h for group in [*settings.get("hooks", {}).get("PostToolUse", []), *settings.get("hooks", {}).get("PreToolUse", [])] for h in group.get("hooks", [])]
    if not hooks:
        return False, "no PostToolUse or PreToolUse hook is registered in .claude/settings.json"
    scripts = found.files.get("hook_scripts", "")
    if not scripts.strip():
        return False, "a hook is registered but no script exists under .claude/hooks/"
    return True, f"{len(hooks)} hook registered, with script(s) {scripts.strip().splitlines()[0]}"


def same_script_runs_in_ci(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    workflows = found.files.get("workflows", "")
    if re.search(r"check-endpoints\.sh", workflows):
        return True, "a workflow runs scripts/check-endpoints.sh on pull requests"
    return False, "no workflow runs the same script on pull requests"
