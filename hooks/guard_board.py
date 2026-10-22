# /// script
# requires-python = ">=3.15"
# ///
"""Keep agents on the shared board's rails (the `asdlc` script's claims and worktrees).

Denied, each with the reason and the way that works instead:

- Editing a file in a board's `backlog/` folder by hand. The board changes through
  `asdlc board`, so each change is committed and pushed where every agent sees it.
- Setting a task to To Do or Done, promoting a draft, or creating a task without
  `--draft` (it would start as accepted To Do work), with `backlog` or `asdlc board`, and
  running `asdlc accept`, which promotes an intent and its draft children. Accepting work
  and closing it are a person's decisions. `asdlc release` and `asdlc reap`, the tool's own
  ways of handing a claimed task back, are allowed. The command `asdlc record-check` runs is
  judged like any other.
- Editing a file in a code repository that takes its work from a board (`git config
  asdlc.board` is set) outside a claimed task's worktree, the one with a `.asdlc-task`
  marker. Work starts with a claim, so no two agents change the same thing.
- `git push` to the default branch of such a code repository. Changes reach it through
  review. Pushes to the board itself are how the board works, so they are allowed.

Shell commands are parsed with shlex, through `&&`, `;`, `|`, subshells, `cd`, env
assignments and `sh -c`. A shell can always do something this doesn't recognise, so it
is a guardrail, not a wall. When the guard can't tell, it allows, logs an error and says
so. Every decision is logged.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePath

from decision_log import Verdict, current_branch, decision, project_dir, record

HOOK = "guard_board"
MARKER = ".asdlc-task"
BOARD_FOLDER = "backlog"
PERSON_STATUSES = frozendict({"todo": "To Do", "done": "Done"})
_SEPARATORS = frozenset(";&|()\n`")
_REDIRECTS = frozenset({">", ">>", "<", "<<", "<<<", ">&", "&>", "<&", ">|", "&>>"})
_LAUNCHERS = frozenset({"env", "sudo", "command", "exec", "time", "nohup", "nice", "npx", "bunx", "uv", "uvx", "run", "python", "python3"})
_LAUNCHER_VALUES = frozenset({"--with", "--python", "-p", "--project", "--directory", "--package", "-u", "-n"})
_SHELLS = frozenset({"sh", "bash", "zsh", "dash"})
_BACKLOG = frozenset({"backlog", "backlog.md"})
_PUSH_VALUES = frozenset({"-o", "--push-option", "--receive-pack", "--exec", "--repo"})
_GIT_VALUES = frozenset({"-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"})
_ALL = "*"


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class Repo:
    root: Path
    is_board: bool
    takes_board_work: bool
    has_marker: bool
    branch: str
    protected: frozenset[str]


Lookup = Callable[[Path], Repo | None]

ALLOW = Outcome(Verdict.ALLOW, "nothing the board guard covers")
ACCEPT_REFUSAL = (
    "asdlc accept promotes an intent and its draft children to accepted work, and accepting work is a "
    "person's decision: ask the person to run asdlc accept <intent-id> in their own terminal."
)


# --- the logic -----------------------------------------------------------------------


def decide_file(path: Path, repo: Repo | None) -> Outcome:
    if repo is None:
        return Outcome(Verdict.ALLOW, "not in a git repository")
    relative = path.relative_to(repo.root) if path.is_relative_to(repo.root) else None
    if repo.is_board and relative is not None and relative.parts[:1] == (BOARD_FOLDER,):
        return Outcome(
            Verdict.DENY,
            f"{relative} is on the board: change the board with asdlc board, so it is committed and "
            "pushed where every agent sees it (for example: asdlc board task edit TASK-1 --notes ...).",
        )
    if repo.takes_board_work and not repo.is_board and not repo.has_marker:
        return Outcome(
            Verdict.DENY,
            f"{repo.root} takes its work from a board, and {path} is not in a claimed task's worktree: "
            "claim a task first: asdlc next or asdlc claim, then work in the worktree it prints.",
        )
    return Outcome(Verdict.ALLOW, "not a board file, and not code outside a claimed worktree")


def simple_commands(command: str) -> list[list[str]]:
    """Split a shell command into simple commands: words only, redirections dropped."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n`")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands: list[list[str]] = [[]]
    skip_next = False
    for token in lexer:
        if skip_next:
            skip_next = False
        elif token in _REDIRECTS:
            skip_next = True
        elif token and set(token) <= _SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [words for words in commands if words]


def _without_assignments(words: Sequence[str]) -> list[str]:
    index = 0
    while index < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[index]):
        index += 1
    return list(words[index:])


def unwrap(words: Sequence[str]) -> list[str]:
    """The command a launcher (env, uv run, python, npx, sudo) actually runs."""
    words = _without_assignments(words)
    while words and PurePath(words[0]).name in _LAUNCHERS or (words and re.fullmatch(r"python3(\.\d+)?", PurePath(words[0]).name)):
        words = words[1:]
        while words and (words[0].startswith("-") or "=" in words[0].split("/")[0]):
            words = words[2:] if words[0] in _LAUNCHER_VALUES else words[1:]
    return words


def status_set(arguments: Sequence[str]) -> str | None:
    """The person's status (To Do or Done) a backlog command sets, if any."""
    for index, word in enumerate(arguments):
        value = None
        if word in ("-s", "--status") and index + 1 < len(arguments):
            value = arguments[index + 1]
        elif word.startswith("--status="):
            value = word.partition("=")[2]
        elif word.startswith("-s") and not word.startswith("--") and len(word) > 2:
            value = word[2:].removeprefix("=")
        if value is not None and (named := PERSON_STATUSES.get(re.sub(r"[\s_-]", "", value).casefold())):
            return named
    return None


def backlog_refusal(arguments: Sequence[str]) -> str | None:
    if named := status_set(arguments):
        return (
            f"setting a task to {named} is a person's decision: To Do accepts work, and Done closes it "
            "after someone who didn't do it has reviewed it. Ask the person; to hand back a task you "
            "claimed, use asdlc release."
        )
    pairs = set(zip(arguments, arguments[1:]))
    if ("draft", "promote") in pairs or ("task", "promote") in pairs:
        return "promoting a draft accepts it as work, which is a person's decision: ask the person to promote it."
    if ("task", "create") in pairs and "--draft" not in arguments:
        return (
            "a task created without --draft starts as accepted To Do work, and accepting work is a "
            "person's decision: add --draft, and the person promotes it."
        )
    return None


def _asdlc_subcommand(arguments: Sequence[str]) -> tuple[str, list[str]]:
    index = 0
    while index < len(arguments):
        if arguments[index] == "--board":
            index += 2
        elif arguments[index].startswith("-"):
            index += 1
        else:
            return arguments[index], list(arguments[index + 1:])
    return "", []


def push_destinations(arguments: Sequence[str], branch: str) -> frozenset[str]:
    """The branches a `git push` writes to, or `*` for every branch."""
    positional: list[str] = []
    every, tags = False, False
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--":
            positional += arguments[index + 1:]
            break
        if word in _PUSH_VALUES:
            index += 2
            continue
        if word in ("--all", "--mirror", "--branches"):
            every = True
        elif word == "--tags":
            tags = True
        elif not word.startswith("-"):
            positional.append(word)
        index += 1
    if every:
        return frozenset({_ALL})
    refspecs = positional[1:]
    if not refspecs:
        return frozenset() if tags or not branch else frozenset({branch})
    destinations = set()
    for refspec in refspecs:
        source, colon, target = refspec.lstrip("+").partition(":")
        name = target if colon else source
        name = branch if name in ("HEAD", "@") else name
        destinations.add(name.removeprefix("refs/heads/"))
    return frozenset(destinations)


def _git_call(words: Sequence[str], directory: Path) -> tuple[str, list[str], Path]:
    """A git command's subcommand, its arguments, and the directory it runs in."""
    index = 1
    while index < len(words) and words[index].startswith("-"):
        word = words[index]
        if word == "-C" and index + 1 < len(words):
            directory = directory / words[index + 1]
            index += 2
        elif word in _GIT_VALUES:
            index += 2
        else:
            index += 1
    if index >= len(words):
        return "", [], directory
    return words[index], list(words[index + 1:]), directory


def decide_command(command: str, cwd: Path, lookup: Lookup) -> Outcome:
    try:
        commands = simple_commands(command)
    except ValueError as error:
        if re.search(r"\b(backlog|asdlc|git\s+push)\b", command):
            return Outcome(Verdict.ERROR, f"could not parse a command that may touch the board or push ({error}); allowed")
        return ALLOW
    directory = cwd
    for words in commands:
        words = _without_assignments(words)
        if words[:1] == ["cd"]:
            directory = directory / (words[1] if len(words) > 1 else str(Path.home()))
            continue
        words = unwrap(words)
        if not words:
            continue
        name = PurePath(words[0]).name
        if name in _SHELLS and "-c" in words[1:-1]:
            inner = decide_command(words[words.index("-c", 1) + 1], directory, lookup)
            if inner.verdict is not Verdict.ALLOW:
                return inner
        elif name in _BACKLOG:
            if reason := backlog_refusal(words[1:]):
                return Outcome(Verdict.DENY, reason)
        elif name == "asdlc":
            subcommand, rest = _asdlc_subcommand(words[1:])
            if subcommand == "board" and (reason := backlog_refusal(rest)):
                return Outcome(Verdict.DENY, reason)
            if subcommand == "accept":
                return Outcome(Verdict.DENY, ACCEPT_REFUSAL)
            if subcommand == "record-check" and "--" in rest:
                inner = decide_command(shlex.join(rest[rest.index("--") + 1:]), directory, lookup)
                if inner.verdict is not Verdict.ALLOW:
                    return inner
        elif name == "git":
            subcommand, rest, where = _git_call(words, directory)
            if subcommand == "push" and (outcome := _decide_push(rest, where, lookup)).verdict is not Verdict.ALLOW:
                return outcome
    return ALLOW


def _decide_push(arguments: Sequence[str], directory: Path, lookup: Lookup) -> Outcome:
    repo = lookup(directory)
    if repo is None or repo.is_board or not repo.takes_board_work:
        return ALLOW
    hits = push_destinations(arguments, repo.branch)
    protected = sorted(repo.protected if _ALL in hits else hits & repo.protected)
    if not protected:
        return ALLOW
    return Outcome(
        Verdict.DENY,
        f"this pushes to {', '.join(protected)} of {repo.root}, which takes its work from a board: "
        "changes reach it through review. Push the task's own branch and open a pull request.",
    )


# --- the shell -----------------------------------------------------------------------


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def _existing(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if candidate.is_dir():
            return candidate
    return None


def _resolved(path: Path) -> Path:
    """The path with symlinks resolved, even when its last folders don't exist yet."""
    anchor = _existing(path.parent)
    return anchor.resolve() / path.relative_to(anchor) if anchor else path


def repo_at(path: Path) -> Repo | None:
    directory = _existing(path)
    if directory is None:
        return None
    top = _git(directory, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    root = Path(top.stdout.strip()).resolve()
    default = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD").stdout.strip()
    return Repo(
        root=root,
        is_board=(root / BOARD_FOLDER / "config.yml").is_file(),
        takes_board_work=_git(root, "config", "--get", "asdlc.board").returncode == 0,
        has_marker=(root / MARKER).is_file(),
        branch=current_branch(root),
        protected=frozenset({"main", "master", *([default.removeprefix("origin/")] if default else [])}),
    )


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
    if tool == "Bash":
        outcome = decide_command(str(tool_input.get("command", "")), cwd, repo_at)
    else:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path")
        if raw:
            path = _resolved(Path(os.path.normpath(cwd / str(raw))))
            outcome = decide_file(path, repo_at(path.parent))
        else:
            outcome = Outcome(Verdict.ALLOW, "no file named")
    record(project, decision(datetime.now(), HOOK, tool, outcome.verdict, outcome.reason, current_branch(project)))
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
