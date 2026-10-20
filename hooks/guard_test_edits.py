# /// script
# requires-python = ">=3.15"
# ///
"""Keep a bug fix from editing the tests that judge it (spec R13).

On a `fix/` branch, a change to a test file that already exists on the branch's base is
denied: the failing test written first is the proof, and a fix that edits it proves
nothing. New test files are allowed. This covers the file tools and shell commands that
plainly write to an existing test (`sed -i`, a redirect, `tee`, `mv`, `rm`, `cp`,
`git checkout --`, `git restore` and similar). A shell can always write a file in a way
this doesn't recognise, so it is a guardrail, not a wall. Every decision is logged.

If the guard can't decide, because no base branch resolves or the guard itself fails, it
allows the change, logs an error and tells the person, so a guard that is off is visible
without stopping all work.
"""

import json
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from decision_log import Verdict, current_branch, decision, project_dir, record

HOOK = "guard_test_edits"
FIX_PREFIX = "fix/"
FALLBACK_BASES = ("main", "master", "trunk")
_TEST_DIRS = frozenset({"test", "tests", "__tests__", "testdata"})
_TEST_NAME = re.compile(
    r"^(test_.*\.py|.*_test\.(py|go|rb|exs?)|.*_spec\.rb|conftest\.py"
    r"|.*\.(test|spec)\.[cm]?[jt]sx?|.*tests?\.(java|kt|swift|cs))$",
    re.IGNORECASE,
)
_SHELL_WRITES = re.compile(
    r"\bsed\b[^|;&]*\s-i|\bperl\b[^|;&]*\s-[a-z]*i|\btee\b|\btruncate\b|\b(mv|rm|cp|install|patch)\b"
    r"|\bgit\s+(checkout|restore|apply|rm|mv)\b"
)
_REDIRECT_TARGET = re.compile(r"(?<![0-9&])>>?\s*([^\s;&|]+)")


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    reason: str


# --- the logic -----------------------------------------------------------------------


def is_test_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return bool(_TEST_NAME.match(path.name)) or any(part.lower() in _TEST_DIRS for part in path.parts[:-1])


def tests_written_by(
    command: str, existing_tests: Collection[str], to_relative: Callable[[str], str]
) -> tuple[str, ...]:
    """Existing test files a shell command plainly writes to.

    A redirect counts only when its target is a test. Any other writing command counts
    when it names a test anywhere in its arguments.
    """
    try:
        words = shlex.split(command, comments=True)
    except ValueError:
        words = command.split()
    named = {to_relative(word) for word in words}
    redirected = {to_relative(target) for target in _REDIRECT_TARGET.findall(command)}
    hits = redirected & set(existing_tests)
    if _SHELL_WRITES.search(command):
        hits |= named & set(existing_tests)
    return tuple(sorted(hits))


def _deny(paths: Collection[str], branch: str) -> Outcome:
    listed = ", ".join(sorted(paths))
    return Outcome(
        Verdict.DENY,
        f"{listed}: an existing test, and this is a fix branch ({branch}). A fix makes the "
        "failing test pass without changing it, so the test still proves the bug is gone. "
        "Add a new test file if more coverage is needed, or ask the person to change this "
        "test themselves.",
    )


def decide_file(branch: str, relative: str | None, exists_on_base: bool | None) -> Outcome:
    if not branch.startswith(FIX_PREFIX):
        return Outcome(Verdict.ALLOW, "not a fix branch")
    if relative is None or not is_test_path(relative):
        return Outcome(Verdict.ALLOW, "not a test file")
    if exists_on_base is None:
        return Outcome(Verdict.ERROR, "no base branch resolved, so the guard could not tell whether this test exists; allowed")
    if not exists_on_base:
        return Outcome(Verdict.ALLOW, "new test file")
    return _deny([relative], branch)


def decide_command(branch: str, written: Collection[str] | None) -> Outcome:
    if not branch.startswith(FIX_PREFIX):
        return Outcome(Verdict.ALLOW, "not a fix branch")
    if written is None:
        return Outcome(Verdict.ERROR, "no base branch resolved, so the guard could not check this command; allowed")
    if not written:
        return Outcome(Verdict.ALLOW, "writes no existing test")
    return _deny(written, branch)


# --- the shell -----------------------------------------------------------------------


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def _root(directory: Path) -> Path | None:
    done = _git(directory, "rev-parse", "--show-toplevel")
    return Path(done.stdout.strip()) if done.returncode == 0 else None


def _relative(root: Path, cwd: Path, raw: str) -> str:
    path = Path(raw)
    absolute = path if path.is_absolute() else cwd / path
    try:
        return absolute.resolve().relative_to(root.resolve()).as_posix()
    except ValueError, OSError:
        return raw


def _base(root: Path) -> str | None:
    """The merge base with the default branch: origin/HEAD first, then common names."""
    head = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    candidates = ([head.stdout.strip()] if head.returncode == 0 else []) + [
        name for base in FALLBACK_BASES for name in (f"origin/{base}", base)
    ]
    for ref in candidates:
        done = _git(root, "merge-base", "HEAD", ref)
        if done.returncode == 0:
            return done.stdout.strip()
    return None


def _tests_on(root: Path, base: str) -> frozenset[str]:
    listed = _git(root, "ls-tree", "-r", "--name-only", base)
    return frozenset(path for path in listed.stdout.splitlines() if is_test_path(path))


def _emit(outcome: Outcome) -> None:
    match outcome.verdict:
        case Verdict.DENY:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": outcome.reason,
            }}))
        case Verdict.ERROR:
            print(json.dumps({"systemMessage": f"asdlc {HOOK}: {outcome.reason}"}))
        case Verdict.ALLOW | Verdict.ASK:
            pass


def main() -> int:
    payload = json.load(sys.stdin)
    tool = str(payload.get("tool_name", ""))
    project = project_dir(payload)
    cwd = Path(str(payload.get("cwd") or project))
    tool_input = payload.get("tool_input") or {}
    root = _root(cwd) or project
    branch = current_branch(root)
    base = _base(root) if branch.startswith(FIX_PREFIX) else None
    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        written = (
            tests_written_by(command, _tests_on(root, base), lambda word: _relative(root, cwd, word))
            if base else None
        )
        outcome = decide_command(branch, written)
    else:
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        relative = _relative(root, cwd, str(file_path)) if file_path else None
        exists = (
            _git(root, "cat-file", "-e", f"{base}:{relative}").returncode == 0
            if base and relative else None
        )
        outcome = decide_file(branch, relative, exists)
    record(project, decision(datetime.now(), HOOK, tool, outcome.verdict, outcome.reason, branch))
    _emit(outcome)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as error:  # a broken guard must be visible, not block all work
        message = f"failed and allowed the change: {type(error).__name__}: {error}"
        print(f"asdlc: {HOOK} {message}", file=sys.stderr)
        print(json.dumps({"systemMessage": f"asdlc {HOOK} {message}"}))
        record(project_dir({}), decision(datetime.now(), HOOK, "", Verdict.ERROR, message, ""))
        code = 0
    raise SystemExit(code)
