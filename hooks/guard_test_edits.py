# /// script
# requires-python = ">=3.15"
# ///
"""Keep a bug fix from editing the tests that judge it (spec R13).

While fixing a bug, a change to a test file that already exists on the branch's base is
denied: the failing test written first is the proof, and a fix that edits it proves
nothing. New test files are allowed. A write is a bug fix when its branch starts with
`fix/`, or when it lands in the worktree of a bug task claimed on the board (its
`.asdlc-task` marker says `"type": "bug"`). The repository is found from the path written
to, not the session's folder: board workers stay in the tasks clone and write their
worktree by absolute path, `git -C` or `asdlc --in`. This covers the file tools and shell commands that
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
MARKER = ".asdlc-task"  # written by asdlc's claim in each task worktree
BUG = "bug"
FALLBACK_BASES = ("main", "master", "trunk")
_TEST_DIRS = frozenset({"test", "tests", "__tests__", "testdata"})
_TEST_NAME = re.compile(
    r"^(test_.*\.py|.*_test\.(py|go|rb|exs?)|.*_spec\.rb|conftest\.py"
    r"|.*\.(test|spec)\.[cm]?[jt]sx?|.*tests?\.(java|kt|swift|cs))$",
    re.IGNORECASE,
)
_SHELL_WRITES = re.compile(
    r"\bsed\b[^|;&]*\s-i|\bperl\b[^|;&]*\s-[a-z]*i|\btee\b|\btruncate\b|\b(mv|rm|cp|install|patch)\b"
    r"|\bgit(?:\s+(?:-C|--git-dir|--work-tree)\s+\S+|\s+-\S+)*\s+(checkout|restore|apply|rm|mv)\b"
)
_REDIRECT_TARGET = re.compile(r"(?<![0-9&])>>?\s*([^\s;&|]+)")


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class Anchor:
    """A folder or path a shell command names: a repository it may write in."""

    path: str
    resolves_relative: bool  # a `-C`/`--in` folder: the command's relative paths are inside it


_STRENGTH = {Verdict.DENY: 3, Verdict.ERROR: 2, Verdict.ASK: 1, Verdict.ALLOW: 0}
_FOLDER_OPTIONS = frozenset({"-C", "--in", "--work-tree"})  # the command's relative paths are inside the folder
_PATH_OPTIONS = frozenset({"--git-dir"})  # names a repository, not where relative paths start
_COPIES = frozenset({"cp", "install"})
_OPERATOR_CHARS = frozenset("&|;()<>")


# --- the logic -----------------------------------------------------------------------


def is_test_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return bool(_TEST_NAME.match(path.name)) or any(part.lower() in _TEST_DIRS for part in path.parts[:-1])


def _segments(command: str) -> list[list[str]]:
    """The simple commands in a shell line, split at `&&`, `||`, `;` and `|` outside quotes."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and set(token) <= _OPERATOR_CHARS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def tests_written_by(
    command: str, existing_tests: Collection[str], to_relative: Callable[[str], str]
) -> tuple[str, ...]:
    """Existing test files a shell command plainly writes to.

    A redirect counts only when its target is a test. A copy (`cp`, `install`) counts
    only when its destination, the last argument, is a test, so copying an existing test
    to start a new one is allowed. Any other writing command counts when it names a test
    anywhere in its arguments.
    """
    existing = set(existing_tests)
    hits = {to_relative(target) for target in _REDIRECT_TARGET.findall(command)} & existing
    for words in _segments(command):
        if not _SHELL_WRITES.search(" ".join(words)):
            continue
        named = words[-1:] if words[0] in _COPIES else words
        hits |= {to_relative(word) for word in named} & existing
    return tuple(sorted(hits))


def bug_task_of(marker: str | None) -> str | None:
    """The task a worktree's marker names, when that task is a bug; None otherwise."""
    if marker is None:
        return None
    try:
        data = json.loads(marker)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("type") != BUG:
        return None
    task = data.get("task")
    return task if isinstance(task, str) and task else None


def _is_fix(branch: str, bug_task: str | None) -> bool:
    return branch.startswith(FIX_PREFIX) or bug_task is not None


def anchors(command: str) -> tuple[Anchor, ...]:
    """The folders (`-C`, `--in`, `--work-tree`, `--git-dir`) and absolute or home paths a
    shell command names, in order. Folders may be relative; the shell resolves them."""
    try:
        words = shlex.split(command, comments=True)
    except ValueError:
        words = command.split()
    found: list[Anchor] = []
    for before, word in zip(["", *words], words):
        option, _, value = word.partition("=")
        if before in _FOLDER_OPTIONS or before in _PATH_OPTIONS:
            found.append(Anchor(word, before in _FOLDER_OPTIONS))
        elif value and (option in _FOLDER_OPTIONS or option in _PATH_OPTIONS):
            found.append(Anchor(value, option in _FOLDER_OPTIONS))
        elif word.startswith("-C") and len(word) > 2:
            found.append(Anchor(word[2:], True))
        elif word.startswith(("/", "~/")) and word not in _FOLDER_OPTIONS | _PATH_OPTIONS:
            found.append(Anchor(word, False))
    return tuple(dict.fromkeys(found))


def strongest(outcomes: Collection[Outcome]) -> Outcome:
    """The verdict that counts across every repository a command writes in: deny, then error, then allow."""
    return max(outcomes, key=lambda o: _STRENGTH[o.verdict], default=Outcome(Verdict.ALLOW, "not in a repository"))


def _deny(paths: Collection[str], branch: str, bug_task: str | None) -> Outcome:
    listed = ", ".join(sorted(paths))
    what = f"bug task {bug_task}'s worktree (branch {branch})" if bug_task else f"a fix branch ({branch})"
    return Outcome(
        Verdict.DENY,
        f"{listed}: an existing test, and this is {what}. A fix makes the "
        "failing test pass without changing it, so the test still proves the bug is gone. "
        "Add a new test file if more coverage is needed, or ask the person to change this "
        "test themselves.",
    )


def decide_file(branch: str, relative: str | None, exists_on_base: bool | None, bug_task: str | None = None) -> Outcome:
    if not _is_fix(branch, bug_task):
        return Outcome(Verdict.ALLOW, "not a fix branch")
    if relative is None or not is_test_path(relative):
        return Outcome(Verdict.ALLOW, "not a test file")
    if exists_on_base is None:
        return Outcome(Verdict.ERROR, "no base branch resolved, so the guard could not tell whether this test exists; allowed")
    if not exists_on_base:
        return Outcome(Verdict.ALLOW, "new test file")
    return _deny([relative], branch, bug_task)


def decide_command(branch: str, written: Collection[str] | None, bug_task: str | None = None) -> Outcome:
    if not _is_fix(branch, bug_task):
        return Outcome(Verdict.ALLOW, "not a fix branch")
    if written is None:
        return Outcome(Verdict.ERROR, "no base branch resolved, so the guard could not check this command; allowed")
    if not written:
        return Outcome(Verdict.ALLOW, "writes no existing test")
    return _deny(written, branch, bug_task)


# --- the shell -----------------------------------------------------------------------


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def _root(directory: Path) -> Path | None:
    done = _git(directory, "rev-parse", "--show-toplevel")
    return Path(done.stdout.strip()) if done.returncode == 0 else None


def _root_of(path: Path) -> Path | None:
    """The repository holding a path, from its nearest folder that exists."""
    folder = path if path.is_dir() else path.parent
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent
    return _root(folder) if folder.is_dir() else None


def _bug_task(root: Path) -> str | None:
    marker = root / MARKER
    try:
        return bug_task_of(marker.read_text()) if marker.is_file() else None
    except OSError:
        return None


def _relative(root: Path, cwd: Path, raw: str) -> str:
    path = Path(raw).expanduser()
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


def _judge_command(command: str, root: Path, relative_to: Path) -> tuple[Outcome, str]:
    """The verdict on a shell command's writes inside one repository, and what to log it under."""
    branch, bug_task = current_branch(root), _bug_task(root)
    base = _base(root) if _is_fix(branch, bug_task) else None
    written = (
        tests_written_by(command, _tests_on(root, base), lambda word: _relative(root, relative_to, word))
        if base else None
    )
    return decide_command(branch, written, bug_task), bug_task or branch


def _judge_file(file_path: str, root: Path, cwd: Path) -> tuple[Outcome, str]:
    branch, bug_task = current_branch(root), _bug_task(root)
    base = _base(root) if _is_fix(branch, bug_task) else None
    relative = _relative(root, cwd, file_path)
    exists = _git(root, "cat-file", "-e", f"{base}:{relative}").returncode == 0 if base else None
    return decide_file(branch, relative, exists, bug_task), bug_task or branch


def main() -> int:
    payload = json.load(sys.stdin)
    tool = str(payload.get("tool_name", ""))
    project = project_dir(payload)
    cwd = Path(str(payload.get("cwd") or project))
    tool_input = payload.get("tool_input") or {}
    here = _root(cwd) or project
    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        places = {(here, cwd)}
        for anchor in anchors(command):
            path = cwd / Path(anchor.path).expanduser()  # an absolute path replaces cwd
            if (root := _root_of(path)) is not None:
                places.add((root, path if anchor.resolves_relative else cwd))
        judged = [_judge_command(command, root, relative_to) for root, relative_to in sorted(places)]
        outcome = strongest([o for o, _ in judged])
        artefact = next((a for o, a in judged if o == outcome), current_branch(here))
    else:
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        root = (_root_of(Path(str(file_path)) if Path(str(file_path)).is_absolute() else cwd / str(file_path)) if file_path else None) or here
        if file_path:
            outcome, artefact = _judge_file(str(file_path), root, cwd)
        else:
            outcome, artefact = decide_file(current_branch(root), None, None), current_branch(root)
    record(project, decision(datetime.now(), HOOK, tool, outcome.verdict, outcome.reason, artefact))
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
