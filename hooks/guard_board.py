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
- Approving, requesting changes on or merging a pull request: `gh pr review --approve` or
  `--request-changes` (`-a`, `-r`), `gh pr merge`, and the same through `gh api` (a pull
  request's `/merge`, a review with event APPROVE or REQUEST_CHANGES, or the GraphQL
  mutations that do either). Approving and merging are a person's; a review comments.

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
STATUSES = frozendict({"todo": "To Do", "done": "Done", "inprogress": "In Progress", "inreview": "In Review"})
PERSON_STATUSES = frozenset({"To Do", "Done"})
REVIEW_LABELS = frozenset({"review-passed", "changes-requested"})
_LABEL_FLAGS = frozenset({"-l", "--label", "--labels", "--add-label", "--remove-label"})
_ASSIGNEE_FLAGS = frozenset({"-a", "--assignee", "--assignees"})
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
MERGE_REFUSAL = (
    "merging a pull request is a person's decision: it is how work reaches the default branch. Leave it to the "
    "person; a clean review labels the task review-passed for them."
)
APPROVAL_REFUSAL = (
    "approving or requesting changes on a pull request is a person's decision, and an agent's review never approves. "
    "Post the findings as a comment (gh pr comment <url> --body ..., or gh pr review <url> --comment --body ...) "
    "and record the verdict with asdlc review-done."
)
_GH_REVIEW_VALUES = frozenset({"-b", "--body", "-F", "--body-file", "-R", "--repo"})
_GH_VERDICTS = frozenset({"-a", "--approve", "-r", "--request-changes"})
_GH_API_VALUES = frozenset({"-X", "--method", "-f", "--raw-field", "-F", "--field", "-H", "--header", "--input", "-q", "--jq",
                            "-t", "--template", "--hostname", "-p", "--preview", "--cache"})
_GH_API_FIELDS = frozenset({"-f", "--raw-field", "-F", "--field"})
_PERSON_EVENTS = frozenset({"APPROVE", "REQUEST_CHANGES"})
ACCEPT_REFUSAL = (
    "asdlc accept promotes an intent and its draft children to accepted work, and accepting work is a "
    "person's decision: ask the person to run asdlc accept <intent-id> in their own terminal."
)

APPROVE_REFUSAL = (
    "asdlc approve records a person's approval of a plan, and approving a plan is the person's decision: show them the "
    "plans and ask them to run asdlc approve <task id>... in their own terminal."
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


_MCP_READS = frozenset({"view", "list", "search", "get", "read", "show", "overview", "guide", "instructions", "help", "board"})
_MCP_WRITES = frozenset({"create", "edit", "update", "delete", "archive", "restore", "add", "remove", "rename", "upsert", "promote", "demote",
                         "complete", "set", "move", "write"})
MCP_REFUSAL = (
    "Backlog.md's MCP server writes the board's files without committing or pushing them, and without asdlc's checks, so "
    "other agents never see the change and the clone is left dirty. Change the board with asdlc board (for example: "
    "asdlc board task edit TASK-1 --append-notes ...) or the asdlc command for the change: claim, finish, release, review-done. "
    "Reading the board through the MCP server is fine."
)


def decide_mcp(tool: str) -> Outcome:
    """A Backlog.md MCP tool: its reads are allowed, and everything else is refused, since it never pushes."""
    server, _, name = tool.removeprefix("mcp__").partition("__")
    if "backlog" not in server.casefold():
        return Outcome(Verdict.ALLOW, "not a Backlog.md MCP tool")
    words = set(name.casefold().split("_"))
    if words & _MCP_READS and not words & _MCP_WRITES:
        return Outcome(Verdict.ALLOW, f"{name} only reads the board")
    return Outcome(Verdict.DENY, MCP_REFUSAL)


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
    """The board status (To Do, In Progress, In Review or Done) a backlog command sets, if any."""
    for index, word in enumerate(arguments):
        value = None
        if word in ("-s", "--status") and index + 1 < len(arguments):
            value = arguments[index + 1]
        elif word.startswith("--status="):
            value = word.partition("=")[2]
        elif word.startswith("-s") and not word.startswith("--") and len(word) > 2:
            value = word[2:].removeprefix("=")
        if value is not None and (named := STATUSES.get(re.sub(r"[\s_-]", "", value).casefold())):
            return named
    return None


def _flag_values(arguments: Sequence[str], flags: frozenset[str]) -> list[str]:
    """The values given to any of `flags`, as `-f v`, `--flag v` or `--flag=v`."""
    found = []
    for index, word in enumerate(arguments):
        flag, equals, value = word.partition("=")
        if flag in flags and equals:
            found.append(value)
        elif word in flags and index + 1 < len(arguments):
            found.append(arguments[index + 1])
    return found


IN_PROGRESS_REFUSAL = (
    "a task goes In Progress only through a claim, which checks that nobody else holds it: asdlc claim <id> --as <worker>, "
    "or asdlc next --as <worker>."
)
IN_REVIEW_REFUSAL = (
    "a task goes to review only through asdlc finish <id> --as <worker> --pr <url> --notes ..., which checks that the "
    "worker still holds it (its claim may have been reaped and taken by someone else) and records its branch."
)
ASSIGNEE_REFUSAL = (
    "who holds a task changes only through asdlc claim, asdlc release, asdlc reap and asdlc review-done, which check the "
    "holder; reserving accepted work for a person is that person's decision."
)
REVIEW_LABEL_REFUSAL = (
    "the review-passed and changes-requested labels are set only by asdlc review-done (a reviewer's verdict on a review it "
    "holds) and changes-requested is removed only by asdlc finish (handing the fixed task back to review)."
)


def backlog_refusal(arguments: Sequence[str]) -> str | None:
    match status_set(arguments):
        case "To Do" | "Done" as named:
            return (
                f"setting a task to {named} is a person's decision: To Do accepts work, and Done closes it "
                "after someone who didn't do it has reviewed it. Ask the person; to hand back a task you "
                "claimed, use asdlc release."
            )
        case "In Progress":
            return IN_PROGRESS_REFUSAL
        case "In Review":
            return IN_REVIEW_REFUSAL
    pairs = set(zip(arguments, arguments[1:]))
    if ("task", "archive") in pairs or ("task", "demote") in pairs:
        return "archiving or demoting accepted work is a person's decision: ask the person."
    if ("task", "edit") in pairs and _flag_values(arguments, _ASSIGNEE_FLAGS):
        return ASSIGNEE_REFUSAL
    labels = {label.strip().lower() for value in _flag_values(arguments, _LABEL_FLAGS) for label in value.split(",")}
    if labels & REVIEW_LABELS:
        return REVIEW_LABEL_REFUSAL
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


def options(arguments: Sequence[str], takes_value: frozenset[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """A command's positional words, and its flags with their values: `-f v`, `-fv`, `--flag v`
    and `--flag=v`. A flag without a value has an empty one."""
    positional: list[str] = []
    found: list[tuple[str, str]] = []
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if word == "--":
            positional += arguments[index:]
            break
        if word.startswith("--"):
            flag, equals, value = word.partition("=")
        elif word.startswith("-") and len(word) > 1:
            flag, equals, value = word[:2], "", word[2:]
        else:
            positional.append(word)
            continue
        if not equals and not value and flag in takes_value and index < len(arguments):
            value = arguments[index]
            index += 1
        found.append((flag, value))
    return positional, found


def _gh_api(arguments: Sequence[str]) -> Outcome | None:
    """A `gh api` call that merges a pull request or submits an approving or changes-requesting review."""
    positional, found = options(arguments, _GH_API_VALUES)
    path = re.sub(r"^https?://[^/]+", "", positional[0] if positional else "").partition("?")[0].strip("/")
    fields = {key.strip().lower(): value for flag, raw in found if flag in _GH_API_FIELDS for key, _, value in [raw.partition("=")]}
    piped = any(flag == "--input" for flag, _ in found)
    method = next((value.upper() for flag, value in reversed(found) if flag in ("-X", "--method")), "POST" if fields or piped else "GET")
    unseen = f"could not see what this gh api call to {path} sends (it reads it from a file or stdin), so it may approve or merge a pull request; allowed"
    if path == "graphql":
        query = fields.get("query", "")
        if piped or query.startswith("@"):
            return Outcome(Verdict.ERROR, unseen)
        if re.search(r"\b(mergePullRequest|enablePullRequestAutoMerge)\b", query):
            return Outcome(Verdict.DENY, MERGE_REFUSAL)
        if re.search(r"\b(addPullRequestReview|submitPullRequestReview)\b", query) and re.search(r"\b(APPROVE|REQUEST_CHANGES)\b", " ".join(fields.values())):
            return Outcome(Verdict.DENY, APPROVAL_REFUSAL)
        return None
    if method == "GET":
        return None
    if re.search(r"(^|/)pulls/[^/]+/merge$", path):
        return Outcome(Verdict.DENY, MERGE_REFUSAL)
    if re.search(r"(^|/)pulls/[^/]+/reviews(/[^/]+/events)?$", path):
        event = fields.get("event", "")
        if event.strip().upper() in _PERSON_EVENTS:
            return Outcome(Verdict.DENY, APPROVAL_REFUSAL)
        if piped or event.startswith("@"):
            return Outcome(Verdict.ERROR, unseen)
    return None


def gh_outcome(arguments: Sequence[str]) -> Outcome | None:
    """Why a `gh` command is a person's to run, or None when it isn't one of those."""
    words = list(arguments)
    while words and words[0].startswith("-"):
        words = words[1:]
    match words[:2]:
        case ["pr", "merge"]:
            return Outcome(Verdict.DENY, MERGE_REFUSAL)
        case ["pr", "review"]:
            _, found = options(words[2:], _GH_REVIEW_VALUES)
            if any(flag in _GH_VERDICTS and value.lower() != "false" for flag, value in found):
                return Outcome(Verdict.DENY, APPROVAL_REFUSAL)
        case ["api", *_]:
            return _gh_api(words[1:])
    return None


def decide_command(command: str, cwd: Path, lookup: Lookup) -> Outcome:
    try:
        commands = simple_commands(command)
    except ValueError as error:
        if re.search(r"\b(backlog|asdlc|git\s+push|gh\s+(pr|api))\b", command):
            return Outcome(Verdict.ERROR, f"could not parse a command that may touch the board, push, approve or merge ({error}); allowed")
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
            if subcommand == "approve":
                return Outcome(Verdict.DENY, APPROVE_REFUSAL)
            if subcommand == "record-check" and "--" in rest:
                inner = decide_command(shlex.join(rest[rest.index("--") + 1:]), directory, lookup)
                if inner.verdict is not Verdict.ALLOW:
                    return inner
        elif name == "gh":
            if (outcome := gh_outcome(words[1:])) is not None:
                return outcome
        elif name == "git":
            subcommand, rest, where = _git_call(words, directory)
            if subcommand == "push" and (outcome := _decide_push(rest, where, lookup)).verdict is not Verdict.ALLOW:
                return outcome
    return ALLOW


def forces(arguments: Sequence[str]) -> bool:
    """Whether a `git push` may overwrite history: --force, -f, --force-with-lease, or a `+refspec`."""
    for word in arguments:
        if word == "--":
            break
        if word.startswith("--force") or (word.startswith("-") and not word.startswith("--") and "f" in word[1:]):
            return True
        if word.startswith("+"):
            return True
    return False


FORCE_REFUSAL = (
    "a force push rewrites a task branch whose history a review, and maybe another worker, builds on. Bring in what is on "
    "origin instead: git fetch origin, then git rebase origin/<branch> (your new commits go on top), and push without force."
)


def _decide_push(arguments: Sequence[str], directory: Path, lookup: Lookup) -> Outcome:
    repo = lookup(directory)
    if repo is None or repo.is_board or not repo.takes_board_work:
        return ALLOW
    if forces(arguments):
        return Outcome(Verdict.DENY, FORCE_REFUSAL)
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
    elif tool.startswith("mcp__"):
        outcome = decide_mcp(tool)
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
