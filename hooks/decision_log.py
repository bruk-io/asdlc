# /// script
# requires-python = ">=3.15"
# ///
"""The hook decision log: one JSON line per decision in `.asdlc/hooks.jsonl` (spec R26).

Every hook records what it decided and why, so prompts, denials and errors can be
counted later instead of noticed by feel. Writing the log never breaks the hook.
"""

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

LOG = Path(".asdlc") / "hooks.jsonl"


class Verdict(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"
    ERROR = "error"


@dataclass(frozen=True)
class Decision:
    time: str
    hook: str
    tool: str
    verdict: Verdict
    reason: str
    artefact: str

    def to_line(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def decision(now: datetime, hook: str, tool: str, verdict: Verdict, reason: str, artefact: str) -> Decision:
    return Decision(now.astimezone(UTC).isoformat(timespec="seconds"), hook, tool, verdict, reason, artefact)


def project_dir(payload: dict[str, object]) -> Path:
    """The project the session works in: Claude Code's variable, else the payload's cwd."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or str(payload.get("cwd") or os.getcwd()))


def current_branch(directory: Path) -> str:
    """The checked-out branch, used as the artefact id until artefacts carry their own."""
    done = subprocess.run(
        ["git", "-C", str(directory), "branch", "--show-current"], capture_output=True, text=True
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def record(project: Path, entry: Decision) -> None:
    """Append one decision. A failure to write goes to stderr and is otherwise ignored."""
    try:
        path = project / LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as log:
            log.write(entry.to_line() + "\n")
    except OSError as error:
        print(f"asdlc: could not write the hook decision log: {error}", file=sys.stderr)
