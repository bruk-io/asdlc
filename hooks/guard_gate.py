# /// script
# requires-python = ">=3.15"
# ///
"""Keep the eval gate honest in a repository that has one (spec R22, R23).

A repository has a gate when it holds the plugin's eval suite and `scripts/eval`; in any
other repository this hook allows everything. Where there is a gate, it denies:

- Writing gate evidence by hand: any file under `.eval-results/` or `.asdlc/`, with the file
  tools and with shell commands that plainly write (`sed -i`, a redirect, `tee`, `mv`, `rm`,
  `cp`). Only `scripts/eval` writes evidence, so a forged report takes a deliberate move
  the hook logs.
- `git push` when a steering path changed since the base (CLAUDE.md, skills, hooks, agents,
  commands) and `scripts/gate_evidence.py` finds no passing report for what is on disk. The
  reason names the command a person runs; the agent stops and asks, because a real run
  spends tokens. A change that touches no steering path needs no evidence.
- `git commit` or `git push` with `--no-verify`, which skips the repository's git hooks.
- An edit that would put a change to the plugin and a change to the eval suite in one
  branch (R23), the same rule `scripts/protected_paths.py` applies on the pull request,
  here before the work is done.

Shell commands are parsed as the board guard parses them. A shell can always write a file in
a way this doesn't recognise, so it is a guardrail, not a wall: the pull request's checks
and the repository's branch protection are the wall. When the guard can't tell, it allows,
logs an error and says so. It only denies or allows, never asks. Every decision is logged.
"""

import json
import os
import re
import shlex
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePath, PurePosixPath

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from decision_log import Verdict, current_branch, decision, project_dir, record  # noqa: E402
from gate_evidence import EVIDENCE_ROOTS, State, changed_since, check_change, has_gate, resolve_base, root_of  # noqa: E402
from guard_board import (  # noqa: E402
    SHELLS,
    directory_of,
    git_call,
    shell_script,
    simple_commands,
    unwrap,
    without_assignments,
)
from guard_test_edits import REDIRECT_TARGET, SHELL_WRITES, segments  # noqa: E402
from protected_paths import violation  # noqa: E402

HOOK = "guard_gate"
HOOK_BYPASS = "--no-verify"


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    reason: str


ALLOW = Outcome(Verdict.ALLOW, "nothing the gate guard covers")


# --- the logic -----------------------------------------------------------------------


def is_evidence(relative: str) -> bool:
    """Whether a path is under a folder only `scripts/eval` and the hooks write."""
    parts = PurePosixPath(relative).parts
    return bool(parts) and parts[0] in EVIDENCE_ROOTS


def evidence_refusal(paths: Sequence[str]) -> Outcome:
    return Outcome(
        Verdict.DENY,
        f"{', '.join(sorted(paths))}: gate evidence and the hook log are written only by scripts/eval and the hooks themselves. "
        "A report you write by hand proves nothing. If the gate has not run, stop and ask the person to run `scripts/eval gate`.",
    )


def shell_evidence_writes(command: str, to_relative: Callable[[str], str]) -> tuple[str, ...]:
    """Evidence paths a shell command plainly writes: a redirect to one, or a writing command naming one."""
    hits = {to_relative(target) for target in REDIRECT_TARGET.findall(command)}
    for words in segments(command):
        if SHELL_WRITES.search(" ".join(words)):
            hits |= {to_relative(word) for word in words}
    return tuple(sorted(path for path in hits if is_evidence(path)))


def bypass_refusal(subcommand: str, arguments: Sequence[str]) -> Outcome | None:
    """`git commit` or `git push --no-verify`, and `git commit -n`, which skip the repository's git hooks."""
    if subcommand not in ("commit", "push"):
        return None
    flags = [word for word in arguments if word.startswith("-")]
    skips = HOOK_BYPASS in flags or (subcommand == "commit" and any(re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", word) for word in flags))
    if not skips:
        return None
    return Outcome(
        Verdict.DENY,
        f"git {subcommand} {HOOK_BYPASS} skips this repository's git hooks, which are part of its gates. Run it without the flag; "
        "if a hook is failing, fix what it reports or ask the person.",
    )


def dry_run(arguments: Sequence[str]) -> bool:
    return any(word in ("-n", "--dry-run") for word in arguments if word.startswith("-")) and "--" not in arguments


def r23_refusal(changed: Sequence[str], target: str) -> Outcome | None:
    """Whether editing `target` leaves the branch changing the plugin and the eval suite together."""
    problem = violation([*changed, target])
    if problem is None:
        return None
    return Outcome(
        Verdict.DENY,
        f"editing {target} would put a change to the plugin and a change to the eval suite in one branch: {problem} "
        "Start the eval change on a branch of its own from main.",
    )


# --- the shell -----------------------------------------------------------------------


def relative_to_root(root: Path, base: Path, raw: str) -> str:
    path = Path(raw).expanduser()
    absolute = path if path.is_absolute() else base / path
    try:
        return absolute.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return raw


def decide_push(root: Path) -> Outcome:
    verdict = check_change(root)
    if verdict.holds:
        return Outcome(Verdict.ALLOW, verdict.line())
    if verdict.state is State.UNKNOWN:
        return Outcome(Verdict.ERROR, f"{verdict.reason}; allowed")
    return Outcome(
        Verdict.DENY,
        f"{verdict.line()}. This push is refused until the eval gate has passed on the steering paths you changed. "
        "Stop and ask the person to run `scripts/eval gate --base main` (it spends tokens, so a person decides), then push again.",
    )


def decide_command(command: str, cwd: Path | None) -> Outcome:
    """The verdict on a shell command, judged in the repository each simple command runs in."""
    try:
        commands = simple_commands(command)
    except ValueError as error:
        if re.search(r"\bgit\s+(push|commit)\b|\.eval-results|\.asdlc", command):
            return Outcome(Verdict.ERROR, f"could not parse a command that may push or write evidence ({error}); allowed")
        return ALLOW
    directory = cwd
    visited = [cwd] if cwd is not None else []
    unsure: Outcome | None = None
    for words in commands:
        words = without_assignments(words)
        if words[:1] == ["cd"]:
            directory = directory_of(directory, words[1] if len(words) > 1 else "~")
            if directory is not None:
                visited.append(directory)
            continue
        outcome = _decide_simple(unwrap(words), directory)
        if outcome.verdict is Verdict.DENY:
            return outcome
        if outcome.verdict is Verdict.ERROR and unsure is None:
            unsure = outcome
    for place in dict.fromkeys(visited):  # redirects are dropped from simple commands, so the whole line is read
        root = root_of(place)
        if root is not None and has_gate(root):
            written = shell_evidence_writes(command, lambda word, root=root, place=place: relative_to_root(root, place, word))
            if written:
                return evidence_refusal(written)
    return unsure or ALLOW


def _decide_simple(words: Sequence[str], directory: Path | None) -> Outcome:
    if not words:
        return ALLOW
    name = PurePath(words[0]).name
    if name in SHELLS and (script := shell_script(words)) is not None:
        return decide_command(script, directory)
    if name != "git":
        return ALLOW
    subcommand, rest, where = git_call(words, directory)
    if where is None:
        return Outcome(Verdict.ERROR, "can't tell which repository this git command runs in (its cd or -C names a variable); allowed")
    root = root_of(where)
    if root is None or not has_gate(root):
        return ALLOW
    if (refusal := bypass_refusal(subcommand, rest)) is not None:
        return refusal
    if subcommand == "push" and not dry_run(rest):
        return decide_push(root)
    return ALLOW


def decide_file(root: Path, cwd: Path, raw: str) -> Outcome:
    if not has_gate(root):
        return ALLOW
    relative = relative_to_root(root, cwd, raw)
    if is_evidence(relative):
        return evidence_refusal([relative])
    base = resolve_base(root)
    if base is None:
        return Outcome(Verdict.ERROR, "no base to tell whether this edit mixes the plugin and the eval suite (no origin/main or main); allowed")
    return r23_refusal(changed_since(root, base), relative) or ALLOW


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
        outcome = decide_command(str(tool_input.get("command", "")), cwd)
    else:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path")
        if raw:
            path = Path(os.path.normpath(cwd / str(raw)))
            root = root_of(path)
            outcome = decide_file(root, cwd, str(raw)) if root else ALLOW
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
