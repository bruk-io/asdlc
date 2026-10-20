# /// script
# requires-python = ">=3.15"
# ///
"""Keep a bug fix from editing the tests that judge it (spec R13).

On a `fix/` branch, an edit to a test file that already exists on the branch's merge
base is denied: the failing test written first is the proof, and a fix that edits it
proves nothing. New test files are allowed. Every decision goes to the decision log.

If the guard itself fails it allows the edit, says so on stderr and logs an error, so a
broken guard is visible without stopping all work.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from decision_log import Verdict, current_branch, decision, project_dir, record

HOOK = "guard_test_edits"
FIX_PREFIX = "fix/"
BASE_REFS = ("origin/main", "main")
_TEST_DIRS = frozenset({"test", "tests", "__tests__", "spec"})
_TEST_NAME = re.compile(
    r"^(test_.*\.py|.*_test\.(py|go|rb|exs?)|.*\.(test|spec)\.[cm]?[jt]sx?|.*Tests?\.(java|kt|swift|cs))$"
)


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    reason: str


# --- the logic -----------------------------------------------------------------------


def is_test_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return bool(_TEST_NAME.match(path.name)) or any(part in _TEST_DIRS for part in path.parts[:-1])


def decide(branch: str, relative: str | None, exists_on_base: bool) -> Outcome:
    if not branch.startswith(FIX_PREFIX):
        return Outcome(Verdict.ALLOW, "not a fix branch")
    if relative is None or not is_test_path(relative):
        return Outcome(Verdict.ALLOW, "not a test file")
    if not exists_on_base:
        return Outcome(Verdict.ALLOW, "new test file")
    return Outcome(
        Verdict.DENY,
        f"{relative} is an existing test, and this is a fix branch ({branch}). "
        "A fix makes the failing test pass without changing it, so the test still proves the bug "
        "is gone. Add a new test file if more coverage is needed, or ask the person to change "
        "this test themselves.",
    )


# --- the shell -----------------------------------------------------------------------


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def _locate(file_path: str, cwd: Path) -> tuple[Path, str] | None:
    """The repository root holding the file, and the file's path relative to it."""
    path = Path(file_path)
    absolute = path if path.is_absolute() else cwd / path
    probe = next((p for p in (absolute.parent, *absolute.parents) if p.is_dir()), cwd)
    done = _git(probe, "rev-parse", "--show-toplevel")
    if done.returncode != 0:
        return None
    root = Path(done.stdout.strip())
    try:
        return root, absolute.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _exists_on_base(root: Path, relative: str) -> bool:
    for ref in BASE_REFS:
        base = _git(root, "merge-base", "HEAD", ref)
        if base.returncode == 0:
            return _git(root, "cat-file", "-e", f"{base.stdout.strip()}:{relative}").returncode == 0
    return False


def main() -> int:
    payload = json.load(sys.stdin)
    tool = str(payload.get("tool_name", ""))
    project = project_dir(payload)
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    located = _locate(str(file_path), project) if file_path else None
    root, relative = located if located else (project, None)
    branch = current_branch(root)
    exists = _exists_on_base(root, relative) if relative and branch.startswith(FIX_PREFIX) else False
    outcome = decide(branch, relative, exists)
    record(project, decision(datetime.now(), HOOK, tool, outcome.verdict, outcome.reason, branch))
    if outcome.verdict is Verdict.DENY:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": outcome.reason,
            }
        }))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as error:  # a broken guard must be visible, not block all work
        print(f"asdlc: {HOOK} failed and allowed the edit: {type(error).__name__}: {error}", file=sys.stderr)
        record(Path.cwd(), decision(datetime.now(), HOOK, "", Verdict.ERROR, str(error), ""))
        code = 0
    raise SystemExit(code)
