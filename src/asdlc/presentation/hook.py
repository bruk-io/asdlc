"""What asdlc hands to the two things that run hooks: Claude Code and git."""

import json
from collections.abc import Sequence

from asdlc.domain.documents import Finding
from asdlc.domain.guard import Ruling

GIT_HOOKS = ("pre-push",)
_MARK = "# written by asdlc hook new"


def push_denial(branch: str, denied: Sequence[Ruling]) -> str:
    """Give the JSON that refuses a push and tells Claude which files, and why."""
    lines = [f"- {ruling.path}: {ruling.reason}" for ruling in denied]
    reason = (
        f"asdlc guard: the branch '{branch}' changes files it may not, so it was "
        "not pushed.\n" + "\n".join(lines)
    )
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def lint_feedback(found: Sequence[Finding]) -> str:
    """Give the JSON that tells Claude what is wrong with the document it just wrote.

    Empty when nothing is wrong, so a clean edit costs the model nothing to read.
    """
    if not found:
        return ""
    lines = [f"- {f.path}: [{f.rule}] {f.message}" for f in found]
    context = (
        "asdlc lint: the document you just wrote has findings. Fix them before "
        "going on.\n" + "\n".join(lines)
    )
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            }
        }
    )


def git_hook(name: str) -> str:
    """Give the script git runs for one of its hooks."""
    assert name in GIT_HOOKS
    return f"""#!/bin/sh
{_MARK} {name}
# Before a push: does this branch change only what its documents on main allow?
# The same check runs on the pull request, where it cannot be skipped.
if ! command -v asdlc >/dev/null 2>&1; then
    echo "asdlc is not on your PATH, so the push was not checked." >&2
    echo "Install it: uv tool install git+https://github.com/bruk-io/asdlc" >&2
    exit 0
fi
exec asdlc branch check
"""


def ours(script: str) -> bool:
    """Say whether a hook file is one asdlc wrote, and so may replace."""
    return _MARK in script
