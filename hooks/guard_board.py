# /// script
# requires-python = ">=3.15"
# ///
"""Keep agents on the shared board's rails (the `asdlc` script's claims and worktrees).

Denied, each with the reason and the way that works instead:

- Editing a file in a board's `backlog/` folder by hand. The board changes through
  `asdlc board`, so each change is committed and pushed where every agent sees it.
- Setting a task to To Do or Done, promoting a draft, archiving or demoting a task, or
  creating a task without `--draft` (it would start as accepted To Do work), with `backlog`
  or `asdlc board`, and running `asdlc accept`, `asdlc approve` or `asdlc permissions
  --write`. Accepting work, approving plans, closing work and changing a person's Claude
  Code settings are a person's decisions. `asdlc release` and `asdlc reap`, the
  tool's own ways of handing a claimed task back, are allowed.
- Setting a task In Progress or In Review, changing a task's assignees, or adding or
  removing the review-passed or changes-requested labels, with `backlog` or `asdlc board`.
  Claims, `asdlc finish`, `asdlc release` and `asdlc review-done` do those, checking who
  holds the task, so a worker whose claim was reaped can't change someone else's task.
- Editing a file in a code repository that takes its work from a board (`git config
  asdlc.board` is set) outside a claimed task's worktree, the one with a `.asdlc-task`
  marker. Work starts with a claim, so no two agents change the same thing.
- `git push` to the default branch of such a code repository, and any force push there.
  Changes reach the default branch through review, and a task branch under review is never
  rewritten. Pushes to the board itself are how the board works, so they are allowed.
- Running git so that it runs a program the command doesn't name, or with configuration
  the command sets: global `-c`, `--config-env` and `--exec-path=<dir>`; `git config` writes;
  `grep -O`/`--open-files-in-pager`; `--upload-pack`, `--receive-pack` and `--exec` (and `-u`
  on clone and ls-remote); `--ext-diff` and `--textconv`; clone's `-c`/`--config` and
  `--template`; `rebase -x`/`--exec`; `difftool`, `mergetool`, `submodule foreach`,
  `bisect run`, `filter-branch` and `instaweb`; and `GIT_*` environment variables set for
  git (`GIT_SSH_COMMAND=`, `GIT_PAGER=`, `GIT_CONFIG_*` ...), in front of it, through
  `env`, or with `export`. The permission rules `asdlc permissions` writes match git
  commands with `*`, which would let any of these through without a prompt.
- Approving, requesting changes on or merging a pull request: `gh pr review --approve` or
  `--request-changes` (`-a`, `-r`), `gh pr merge`, and the same through `gh api` (a pull
  request's `/merge`, a review with event APPROVE or REQUEST_CHANGES, or the GraphQL
  mutations that do either). Approving and merging are a person's; a review comments.

Shell commands are parsed with shlex, through `&&`, `;`, `|`, subshells, loops and
conditionals, `cd` and `git -C` (with `~` expanded), env assignments, `xargs`, and
`sh -c`/`bash -lc`. The command `asdlc record-check` runs is judged like any other. A
shell can always do something this doesn't recognise, so it is a guardrail, not a wall.
When the guard can't tell (a `cd` to a variable, a request body it can't see), it allows,
logs an error and says so. It only ever denies or allows, never asks, so it adds no
permission prompts of its own. Every decision is logged.
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
_LAUNCHERS = frozenset({"env", "sudo", "command", "exec", "time", "nohup", "nice", "npx", "bunx", "uv", "uvx", "run", "python", "python3", "xargs"})
_LAUNCHER_VALUES = frozenset({"--with", "--python", "-p", "--project", "--directory", "--package", "-u", "-n",
                              "-I", "-P", "-L", "-d", "-E", "-s", "-a", "--max-args", "--max-procs", "--delimiter", "--arg-file"})
_KEYWORDS = frozenset({"if", "then", "else", "elif", "fi", "for", "select", "while", "until", "do", "done", "case", "esac", "{", "}", "!"})
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

PERMISSIONS_REFUSAL = (
    "asdlc permissions --write changes the person's own Claude Code settings, which is theirs to do: show them "
    "asdlc permissions and ask them to run asdlc permissions --write in their own terminal."
)


GIT_PROGRAM_REFUSAL = (
    "{what} makes git run a program this command doesn't name, or with configuration it sets, and the permission rules for "
    "background agents can't tell that apart from the git they allow. Run git plainly (git -C <worktree> <subcommand> ...); "
    "if the work really needs it, ask the person to run it."
)
_GIT_CONFIG_READS = frozenset({"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--get-color", "--get-colorbool", "-l", "--list",
                               "--show-origin", "--show-scope", "--name-only"})
_GIT_CONFIG_WRITES = frozenset({"--add", "--unset", "--unset-all", "--replace-all", "--rename-section", "--remove-section", "-e", "--edit"})
_GIT_CONFIG_VALUES = frozenset({"-f", "--file", "--blob", "--type", "--default", "--comment", "--value", "--fixed-value"})
_GIT_FETCHERS = frozenset({"fetch", "pull", "push", "clone", "ls-remote", "archive", "submodule"})
_GIT_ENV_PREFIX = "GIT_"


# The short options that take a value, per subcommand: in a cluster such as `-eO`, what follows one is its value.
_SHORT_VALUES = frozendict({"grep": "efABCm", "clone": "obucj", "ls-remote": "u", "rebase": "xsX", "init": ""})


def _short_flags(word: str, takes_value: str) -> str:
    """The short options a word such as `-nO` or `-Ovim` sets, up to and including the first that takes a value."""
    if not word.startswith("-") or word.startswith("--") or len(word) < 2:
        return ""
    letters = ""
    for letter in word[1:]:
        if not letter.isalpha():
            break
        letters += letter
        if letter in takes_value:
            break
    return letters


def _short_cluster_has(word: str, letter: str, subcommand: str) -> bool:
    """Whether a short-option word of this git subcommand sets `letter`, alone (`-O`), clustered (`-nO`) or with its value (`-Ovim`)."""
    return letter in _short_flags(word, _SHORT_VALUES.get(subcommand, ""))


def git_env_refusal(names: Iterable[str]) -> str | None:
    """Why setting these environment variables for git is refused, or None."""
    found = sorted({name for name in names if name.startswith(_GIT_ENV_PREFIX)})
    return GIT_PROGRAM_REFUSAL.format(what=f"setting {', '.join(found)}") if found else None


def git_config_writes(arguments: Sequence[str]) -> bool:
    """Whether a `git config` call sets or removes configuration, in the old form or the new (`git config set ...`)."""
    positional, found = options(arguments, _GIT_CONFIG_VALUES)
    flags = {flag for flag, _ in found}
    if positional[:1] and positional[0] in ("set", "unset", "rename-section", "remove-section", "edit"):
        return True
    if positional[:1] and positional[0] in ("get", "list"):
        return False
    if flags & _GIT_CONFIG_WRITES:
        return True
    return not (flags & _GIT_CONFIG_READS) and len(positional) >= 2


def git_program_refusal(words: Sequence[str]) -> str | None:
    """Why a git command (words[0] is git) is refused for running a program or setting configuration, or None."""
    index = 1
    while index < len(words) and words[index].startswith("-"):
        word = words[index]
        if word == "-c" or (word.startswith("-c") and not word.startswith("--")):
            return GIT_PROGRAM_REFUSAL.format(what="git -c")
        if word == "--config-env" or word.startswith("--config-env="):
            return GIT_PROGRAM_REFUSAL.format(what="git --config-env")
        if word.startswith("--exec-path="):
            return GIT_PROGRAM_REFUSAL.format(what="git --exec-path=<dir>")
        index += 2 if word in _GIT_VALUES or word == "-C" else 1
    if index >= len(words):
        return None
    subcommand, rest = words[index], list(words[index + 1:])
    if "--" in rest:
        rest = rest[:rest.index("--")]
    if subcommand in ("difftool", "mergetool", "filter-branch", "instaweb"):
        return GIT_PROGRAM_REFUSAL.format(what=f"git {subcommand}")
    if subcommand == "submodule" and "foreach" in rest:
        return GIT_PROGRAM_REFUSAL.format(what="git submodule foreach")
    if subcommand == "bisect" and rest[:1] == ["run"]:
        return GIT_PROGRAM_REFUSAL.format(what="git bisect run")
    if subcommand == "config" and git_config_writes(rest):
        return GIT_PROGRAM_REFUSAL.format(what="git config setting a value")
    takes_value = _SHORT_VALUES.get(subcommand, "")
    skip = False
    for word in rest:
        if skip:  # the value of the option before it, such as the pattern after grep -e
            skip = False
            continue
        flag = word.partition("=")[0]
        letters = _short_flags(word, takes_value)
        skip = bool(letters) and letters[-1] in takes_value and len(word) == len(letters) + 1
        if flag in ("--ext-diff", "--textconv"):
            return GIT_PROGRAM_REFUSAL.format(what=f"git {subcommand} {flag}")
        if subcommand == "grep" and (flag == "--open-files-in-pager" or _short_cluster_has(word, "O", subcommand)):
            return GIT_PROGRAM_REFUSAL.format(what="git grep -O (--open-files-in-pager)")
        if subcommand in _GIT_FETCHERS and flag in ("--upload-pack", "--receive-pack", "--exec"):
            return GIT_PROGRAM_REFUSAL.format(what=f"git {subcommand} {flag}")
        if subcommand in ("clone", "ls-remote") and _short_cluster_has(word, "u", subcommand):
            return GIT_PROGRAM_REFUSAL.format(what=f"git {subcommand} -u (--upload-pack)")
        if subcommand in ("clone", "init") and (flag in ("--config", "--template") or (subcommand == "clone" and _short_cluster_has(word, "c", subcommand))):
            return GIT_PROGRAM_REFUSAL.format(what=f"git {subcommand} {flag if flag.startswith('--') else '-c'}")
        if subcommand == "rebase" and (flag == "--exec" or _short_cluster_has(word, "x", subcommand)):
            return GIT_PROGRAM_REFUSAL.format(what="git rebase --exec (-x)")
    return None


_SETTERS = frozenset({"env", "export", "declare", "typeset", "readonly"})
_SETTER_VALUES = frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"})
_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")


def env_names(words: Sequence[str]) -> list[str]:
    """The variables a simple command sets: its leading assignments, and those `env`, `export` or `declare` take."""
    names: list[str] = []
    index = 0
    while index < len(words) and (words[index] in _KEYWORDS or _ASSIGNMENT.match(words[index])):
        if found := _ASSIGNMENT.match(words[index]):
            names.append(found[1])
        index += 1
    if index < len(words) and PurePath(words[index]).name in _SETTERS:
        index += 1
        while index < len(words) and (words[index].startswith("-") or _ASSIGNMENT.match(words[index])):
            if found := _ASSIGNMENT.match(words[index]):
                names.append(found[1])
            index += 2 if words[index] in _SETTER_VALUES else 1
    return names


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
    """The words without leading assignments and shell keywords (`do`, `then`, `{`, `!` ...), so the
    command inside a loop or a conditional is judged like any other."""
    index = 0
    while index < len(words) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[index]) or words[index] in _KEYWORDS):
        index += 1
    return list(words[index:])


def directory_of(base: Path | None, raw: str) -> Path | None:
    """Where `cd <raw>` or `git -C <raw>` leads from `base`, with `~` expanded; None when it can't be
    told, because the path holds a variable or a command substitution."""
    if "$" in raw or "`" in raw:
        return None
    if raw == "~" or raw.startswith("~/"):
        return Path.home() / raw[2:]
    if Path(raw).is_absolute():
        return Path(raw)
    return base / raw if base is not None else None


def unwrap(words: Sequence[str]) -> list[str]:
    """The command a launcher (env, uv run, python, npx, sudo) actually runs."""
    words = _without_assignments(words)
    while words and PurePath(words[0]).name in _LAUNCHERS or (words and re.fullmatch(r"python3(\.\d+)?", PurePath(words[0]).name)):
        words = words[1:]
        while words and (words[0].startswith("-") or "=" in words[0].split("/")[0]):
            words = words[2:] if words[0] in _LAUNCHER_VALUES else words[1:]
    return words


def _flag_values(arguments: Sequence[str], flags: frozenset[str]) -> list[str]:
    """The values given to any of `flags`, as `-f v`, `-fv`, `--flag v` or `--flag=v`."""
    found = []
    for index, word in enumerate(arguments):
        flag, equals, value = word.partition("=")
        if flag in flags and equals:
            found.append(value)
        elif word in flags and index + 1 < len(arguments):
            found.append(arguments[index + 1])
        elif not word.startswith("--") and len(word) > 2 and word[:2] in flags:
            found.append(word[2:].removeprefix("="))
    return found


def status_set(arguments: Sequence[str]) -> str | None:
    """The board status (To Do, In Progress, In Review or Done) a backlog command sets, if any."""
    for value in _flag_values(arguments, frozenset({"-s", "--status"})):
        if named := STATUSES.get(re.sub(r"[\s_-]", "", value).casefold()):
            return named
    return None


def _action(arguments: Sequence[str]) -> tuple[str, str, list[str]]:
    """A backlog command's entity, verb and the words after them: `task edit 1 -s x` is (task, edit, [1, -s, x])."""
    words = [w for w in arguments]
    positional = [index for index, word in enumerate(words) if not word.startswith("-")][:2]
    if len(positional) < 2:
        return (words[positional[0]] if positional else ""), "", words[positional[0] + 1:] if positional else []
    return words[positional[0]], words[positional[1]], words[positional[1] + 1:]


_CHANGES = frozenset({("task", "edit"), ("task", "create"), ("draft", "create"), ("draft", "edit")})


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


SIZE_REFUSAL = (
    "a task's size decides whether its plan needs a person's approval and which model builds it, and an approval records the "
    "size it approved: an agent doesn't change the size of accepted work. Ask the person to resize it; a resized task's plan "
    "is approved again with asdlc approve. Change other labels with --add-label and --remove-label."
)


def _accepted_ids(rest: Sequence[str]) -> list[str]:
    """The ids a `task edit` names that aren't drafts."""
    ids = []
    for word in rest:
        if word.startswith("-"):
            break
        if not re.fullmatch(r"(?i)draft-\d+", word):
            ids.append(word)
    return ids


def backlog_refusal(arguments: Sequence[str]) -> str | None:
    """Why an agent may not run this backlog command, or None. Listings, views and searches are
    never refused: the status, label and assignee rules apply only to commands that change a task."""
    entity, verb, rest = _action(arguments)
    if (entity, verb) in (("draft", "promote"), ("task", "promote")):
        return "promoting a draft accepts it as work, which is a person's decision: ask the person to promote it."
    if (entity, verb) in (("task", "archive"), ("task", "demote")):
        return "archiving or demoting accepted work is a person's decision: ask the person."
    if (entity, verb) not in _CHANGES:
        return None
    match status_set(rest):
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
    if (entity, verb) == ("task", "edit") and _flag_values(rest, _ASSIGNEE_FLAGS):
        return ASSIGNEE_REFUSAL
    labels = {label.strip().lower() for value in _flag_values(rest, _LABEL_FLAGS) for label in value.split(",")}
    if labels & REVIEW_LABELS:
        return REVIEW_LABEL_REFUSAL
    if (entity, verb) == ("task", "edit") and _accepted_ids(rest):
        replacing = _flag_values(rest, frozenset({"-l", "--label", "--labels"})) or "--clear-labels" in rest
        if replacing or any(label.startswith("size-") for label in labels):
            return SIZE_REFUSAL
    if (entity, verb) == ("task", "create") and "--draft" not in rest:
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


def _git_call(words: Sequence[str], directory: Path | None) -> tuple[str, list[str], Path | None]:
    """A git command's subcommand, its arguments, and the directory it runs in (None when it can't be told)."""
    index = 1
    while index < len(words) and words[index].startswith("-"):
        word = words[index]
        if word == "-C" and index + 1 < len(words):
            directory = directory_of(directory, words[index + 1])
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


def _shell_script(words: Sequence[str]) -> str | None:
    """The script `sh -c`, `bash -lc` or `sh -ec` runs, or None."""
    for index, word in enumerate(words[1:-1], start=1):
        if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word):
            return words[index + 1]
    return None


def decide_command(command: str, cwd: Path | None, lookup: Lookup) -> Outcome:
    """The verdict on a shell command: the first refusal among its simple commands, else the first
    thing it couldn't tell (allowed, and said), else allowed."""
    try:
        commands = simple_commands(command)
    except ValueError as error:
        if re.search(r"\b(backlog|asdlc|git\s+push|gh\s+(pr|api))\b", command):
            return Outcome(Verdict.ERROR, f"could not parse a command that may touch the board, push, approve or merge ({error}); allowed")
        return ALLOW
    directory = cwd
    unsure: Outcome | None = None
    for words in commands:
        if reason := git_env_refusal(env_names(words)):  # GIT_* only ever changes what git does
            return Outcome(Verdict.DENY, reason)
        words = _without_assignments(words)
        if words[:1] == ["cd"]:
            directory = directory_of(directory, words[1] if len(words) > 1 else "~")
            continue
        outcome = _decide_simple(unwrap(words), directory, lookup)
        if outcome.verdict is Verdict.DENY:
            return outcome
        if outcome.verdict is Verdict.ERROR and unsure is None:
            unsure = outcome
    return unsure or ALLOW


def _decide_simple(words: Sequence[str], directory: Path | None, lookup: Lookup) -> Outcome:
    if not words:
        return ALLOW
    name = PurePath(words[0]).name
    if name in _SHELLS and (script := _shell_script(words)) is not None:
        return decide_command(script, directory, lookup)
    if name in _BACKLOG:
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
        if subcommand == "permissions" and "--write" in rest:
            return Outcome(Verdict.DENY, PERMISSIONS_REFUSAL)
        if subcommand == "record-check" and "--" in rest:
            return decide_command(shlex.join(rest[rest.index("--") + 1:]), directory, lookup)
    elif name == "gh":
        if (outcome := gh_outcome(words[1:])) is not None:
            return outcome
    elif name == "git":
        if reason := git_program_refusal(words):
            return Outcome(Verdict.DENY, reason)
        subcommand, rest, where = _git_call(words, directory)
        if subcommand == "push":
            return _decide_push(rest, where, lookup)
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


def _decide_push(arguments: Sequence[str], directory: Path | None, lookup: Lookup) -> Outcome:
    if directory is None:
        return Outcome(Verdict.ERROR, "can't tell which repository this git push runs in (its cd or -C names a variable), so it may push to a "
                                      "default branch or force a task branch; allowed")
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
