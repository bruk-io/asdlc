# /// script
# requires-python = ">=3.15"
# ///
"""Put the team's rules, and the code repository's own, in front of the agent working on it.

Code repositories carry no agent setup: the conventions live in the tasks repository (the
board), as plugins. Claude Code loads a plugin's skills but not its rules, so this hook
delivers them.

- PostToolUse on Read, Edit, Write and NotebookEdit: find the code repository holding the
  file, then its board ($ASDLC_BOARD, else `git config asdlc.board` in that repository: the
  order `asdlc` and `asdlc-plugin` use, after their `--board`).
  Each rule in the board's `plugins/team/rules/*.md`, and in `plugins/<repo-slug>/rules/*.md`
  for this repository, whose frontmatter `paths` match the file (relative to the
  repository's root; no `paths` matches every file) and that this context hasn't had yet,
  is returned as additionalContext. A repository rule names the file's layer, from the
  repository plugin's `layers.toml`. The whole injection is capped at 10,000 characters; a
  rule cut short, or left out, says where it is in full. `{plugin_root}` in a rule's body
  becomes its plugin's folder in the board clone, so a rule can name a file beside it.
- SessionStart (startup, clear, compact): the main context has lost what it was given, so
  forget it and deliver again on the next touch.

"This context" is the session, or one subagent in it (`agent_id`): a worker doesn't see what
its orchestrator was given. What was delivered is kept in one small JSON file per session
under ${XDG_STATE_HOME:-~/.local/state}/asdlc/rules/. Delivery comes first and the record
second, so a rule may arrive twice but never fails to arrive.

A file in no repository, in the board itself, or in a repository with no board gets
nothing. Every injection and every error is logged; a failure never blocks the tool call.
"""

import fcntl
import functools
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))

from decision_log import Verdict, current_branch, decision, project_dir, record  # noqa: E402
from repo_slug import slug_of  # noqa: E402

HOOK = "load_rules"
CAP = 10_000
TEAM = "team"
MAIN = "main"
PLUGIN_ROOT = "{plugin_root}"  # in a rule's body: its plugin's folder in the board clone
RESET_SOURCES = frozenset({"startup", "clear", "compact"})
STALE_SECONDS = 14 * 24 * 3600
_MIN_CUT = 400  # below this, a rule cut short says less than its pointer does


class RuleError(ValueError):
    """A rule or layers file this hook can't read; the message says what to fix."""


@dataclass(frozen=True)
class Rule:
    path: Path  # absolute, in the board clone; also the rule's identity in the seen set
    scope: str  # "team", or the code repository's slug
    paths: tuple[str, ...]  # empty: every file in the repository
    body: str


@dataclass(frozen=True)
class Touch:
    """The touched file, relative to its code repository's root, and where the rules are."""

    relative: str
    repo: Path
    board: Path
    slug: str | None


# --- the logic: data in, data out -------------------------------------------------------


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    return raw


def _flow(raw: str) -> list[str]:
    """A YAML flow list of globs, `["a", 'b', c]`. Globs may hold commas inside braces."""
    items, current, depth, quote = [], "", 0, ""
    for char in raw.strip()[1:-1]:
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(current)
            current = ""
            continue
        current += char
    items.append(current)
    return [value for item in items if (value := _unquote(item))]


def parse_rule(path: Path, scope: str, text: str) -> Rule:
    """A rule file: optional frontmatter whose `paths` is a list of globs, then the body.

    `paths` is a block list (one `- glob` per line), a flow list (`[a, b]`) or one glob.
    Other frontmatter keys are ignored.

    Raises:
        RuleError: the frontmatter isn't closed, or `paths` is empty or not a list of globs.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return Rule(path, scope, (), text.strip())
    end = next((n for n, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        raise RuleError(f"{path}: the frontmatter opened with --- is never closed")
    globs: list[str] | None = None
    in_paths = False
    for line in lines[1:end]:
        if in_paths and line.strip().startswith("- "):
            globs.append(_unquote(line.strip()[2:]))
            continue
        if in_paths and (not line.strip() or line.lstrip().startswith("#")):
            continue
        in_paths = False
        key, separator, value = line.partition(":")
        if separator and key.strip() == "paths" and not key[:1].isspace():
            value = value.strip()
            if value.startswith("["):
                globs = _flow(value)
            elif value:
                globs = [_unquote(value)]
            else:
                globs, in_paths = [], True
    if globs is not None and not [g for g in globs if g]:
        raise RuleError(f"{path}: `paths` lists no globs, so the rule would never apply. List globs, one `- \"glob\"` per line, or remove `paths` to apply it to every file")
    body = "\n".join(lines[end + 1:]).strip()
    return Rule(path, scope, tuple(g for g in (globs or ()) if g), body)


def _expand_braces(glob: str) -> list[str]:
    """`a/{b,c}/*.{py,pyi}` as the four globs it stands for. Braces may nest."""
    start = glob.find("{")
    if start < 0:
        return [glob]
    depth = 0
    for end in range(start, len(glob)):
        depth += {"{": 1, "}": -1}.get(glob[end], 0)
        if depth == 0:
            break
    else:
        return [glob]  # an unclosed brace is literal
    options, current, depth = [], "", 0
    for char in glob[start + 1:end]:
        if char == "," and depth == 0:
            options.append(current)
            current = ""
            continue
        depth += {"{": 1, "}": -1}.get(char, 0)
        current += char
    options.append(current)
    return [expanded for option in options for expanded in _expand_braces(glob[:start] + option + glob[end + 1:])]


@functools.cache
def glob_pattern(glob: str) -> re.Pattern[str]:
    """A glob relative to a repository's root as a regex over whole POSIX paths.

    `**/` is any number of folders (none included), `**` is anything, `*` is anything
    within one folder, `?` one character, `{a,b}` either. A glob ending in `/` is
    everything under that folder.
    """
    alternatives = []
    for single in _expand_braces(glob.strip().removeprefix("./").lstrip("/")):
        single = single + "**" if single.endswith("/") else single
        out, index = [], 0
        while index < len(single):
            if single.startswith("**/", index):
                out.append("(?:.*/)?")
                index += 3
            elif single.startswith("**", index):
                out.append(".*")
                index += 2
            elif single[index] == "*":
                out.append("[^/]*")
                index += 1
            elif single[index] == "?":
                out.append("[^/]")
                index += 1
            else:
                out.append(re.escape(single[index]))
                index += 1
        alternatives.append("".join(out))
    return re.compile("|".join(f"(?:{a})" for a in alternatives))


def matches(relative: str, globs: Sequence[str]) -> bool:
    """Whether a path relative to the repository's root matches; no globs matches everything."""
    return not globs or any(glob_pattern(glob).fullmatch(relative) for glob in globs)


def parse_layers(text: str) -> dict[str, tuple[str, ...]]:
    """`layers.toml`: each `[layers.<name>]` table has `paths`, a list of globs. In file order.

    Raises:
        RuleError: the TOML is invalid, or a layer has no list of globs.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise RuleError(f"layers.toml is not valid TOML: {error}") from None
    layers = data.get("layers", {})
    if not isinstance(layers, dict):
        raise RuleError("layers.toml: `layers` must be a table of [layers.<name>] tables")
    found = {}
    for name, table in layers.items():
        paths = table.get("paths") if isinstance(table, dict) else None
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
            raise RuleError(f"layers.toml: [layers.{name}] needs `paths`, a list of globs")
        found[name] = tuple(paths)
    return found


def layer_of(relative: str, layers: Mapping[str, Sequence[str]]) -> str | None:
    """The first layer, in file order, whose globs match the path."""
    return next((name for name, globs in layers.items() if any(glob_pattern(g).fullmatch(relative) for g in globs)), None)


def due(rules: Iterable[Rule], relative: str, seen: Iterable[str]) -> tuple[Rule, ...]:
    """The rules that match the path and that this context hasn't had."""
    had = frozenset(seen)
    return tuple(rule for rule in rules if str(rule.path) not in had and matches(relative, rule.paths))


def _name(rule: Rule) -> str:
    return f"{'team' if rule.scope == TEAM else rule.scope} rule `{rule.path.stem}`"


def injection(rules: Sequence[Rule], relative: str, repo: str, layer: str | None, cap: int = CAP) -> str:
    """The additionalContext for the rules due now, never longer than `cap` characters.

    Each rule comes whole while it fits. One that doesn't is cut, ending with where it is in
    full; when there is too little room even for that, only the pointer is given. Room is
    always kept for the pointers of the rules after it.
    """
    header = f"[asdlc] Rules for {relative} in {repo}, from the tasks repository. Follow them while you work on matching files."
    pointers = [f"\n\n{_name(rule)} also applies here: read it in full at {rule.path}" for rule in rules]
    text = header
    for index, rule in enumerate(rules):
        reserve = sum(len(p) for p in pointers[index + 1:])
        where = f" - this file is in the `{layer}` layer" if layer and rule.scope != TEAM else ""
        heading = f"\n\n[asdlc] {_name(rule)} ({rule.path}){where}\n\n"
        note = f"\n\n[Cut short to keep the rules under {cap:,} characters. Read the rest at {rule.path}]"
        room = cap - len(text) - reserve
        body = rule.body.replace(PLUGIN_ROOT, str(rule.path.parent.parent))
        if len(heading) + len(body) <= room:
            text += heading + body
        elif room - len(heading) - len(note) >= _MIN_CUT:
            text += heading + body[:room - len(heading) - len(note)].rstrip() + note
        else:
            text += pointers[index]
    return text[:cap]


def state_key(agent_id: object) -> str:
    return str(agent_id) if agent_id else MAIN


def forget(state: Mapping[str, list[str]], source: str) -> dict[str, list[str]]:
    """What is still in context after a SessionStart: nothing for the main context on a
    clear or compact; nothing at all on a startup, which may reuse an old session id."""
    if source == "startup":
        return {}
    if source in RESET_SOURCES:
        return {key: value for key, value in state.items() if key != MAIN}
    return dict(state)


# --- the shell: git, files, stdin and stdout ---------------------------------------------


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def _existing(path: Path) -> Path | None:
    return next((candidate for candidate in (path, *path.parents) if candidate.is_dir()), None)


def _is_board(path: Path) -> bool:
    return (path / "backlog" / "config.yml").is_file()


def locate(file: Path, environ: Mapping[str, str]) -> Touch | None:
    """The code repository and board for a touched file, or None when it gets no rules."""
    directory = _existing(file.parent)
    if directory is None:
        return None
    top = _git(directory, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    repo = Path(top.stdout.strip()).resolve()
    if _is_board(repo):
        return None
    raw = environ.get("ASDLC_BOARD", "").strip()
    if not raw:
        configured = _git(repo, "config", "--get", "asdlc.board")
        raw = configured.stdout.strip() if configured.returncode == 0 else ""
    if not raw:
        return None
    board = Path(raw).expanduser()
    board = (board if board.is_absolute() else repo / board).resolve()
    if not board.is_dir() or board == repo:
        return None
    try:
        relative = file.resolve().relative_to(repo).as_posix()
    except ValueError:
        return None
    return Touch(relative, repo, board, slug_of(repo))


def _rules_in(folder: Path, scope: str) -> tuple[list[Rule], list[str]]:
    rules, errors = [], []
    for path in sorted(folder.glob("*.md"), key=lambda p: p.stem) if folder.is_dir() else ():
        try:
            rules.append(parse_rule(path, scope, path.read_text()))
        except (RuleError, OSError, UnicodeDecodeError) as error:
            errors.append(str(error))
    return rules, errors


def _layer(touch: Touch) -> tuple[str | None, list[str]]:
    if touch.slug is None:
        return None, []
    path = touch.board / "plugins" / touch.slug / "layers.toml"
    if not path.is_file():
        return None, []
    try:
        return layer_of(touch.relative, parse_layers(path.read_text())), []
    except (RuleError, OSError, UnicodeDecodeError) as error:
        return None, [f"{path}: {error}"]


def state_file(payload: Mapping[str, object], environ: Mapping[str, str]) -> Path:
    base = Path(environ.get("XDG_STATE_HOME") or Path(environ.get("HOME") or Path.home()) / ".local" / "state")
    session = re.sub(r"[^\w.-]", "_", str(payload.get("session_id") or "unknown"))
    return base / "asdlc" / "rules" / f"{session}.json"


def _update_state(path: Path, change) -> dict[str, list[str]]:
    """Read, change and write the session's state file under a lock; returns the old state.

    Raises:
        OSError: the file can't be read or written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        try:
            loaded = json.loads(handle.read() or "{}")
        except ValueError:
            loaded = {}
        old = {str(k): [str(i) for i in v] for k, v in loaded.items() if isinstance(v, list)} if isinstance(loaded, dict) else {}
        new = change(old)
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(new, indent=1, sort_keys=True))
        return old


def _seen(path: Path, key: str) -> list[str]:
    try:
        loaded = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    value = loaded.get(key, []) if isinstance(loaded, dict) else []
    return [str(item) for item in value] if isinstance(value, list) else []


def _prune(folder: Path, now: float) -> None:
    """Drop the state of sessions untouched for two weeks."""
    for old in folder.glob("*.json") if folder.is_dir() else ():
        try:
            if now - old.stat().st_mtime > STALE_SECONDS:
                old.unlink()
        except OSError:
            pass


@dataclass(frozen=True)
class Result:
    output: dict[str, object] | None
    verdict: Verdict | None  # None: nothing decided, nothing logged
    reason: str


def on_tool_use(payload: Mapping[str, object], environ: Mapping[str, str]) -> Result:
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return Result(None, None, "no file named")
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return Result(None, None, "no file named")
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    touch = locate(Path(os.path.normpath(cwd / str(raw))), environ)
    if touch is None:
        return Result(None, None, "no code repository with a board")
    key = state_key(payload.get("agent_id"))
    state = state_file(payload, environ)
    seen = _seen(state, key)
    rules, errors = _rules_in(touch.board / "plugins" / TEAM / "rules", TEAM)
    if touch.slug is not None:
        repo_rules, repo_errors = _rules_in(touch.board / "plugins" / touch.slug / "rules", touch.slug)
        rules, errors = rules + repo_rules, errors + repo_errors
    chosen = due(rules, touch.relative, seen)
    layer, layer_errors = _layer(touch) if any(rule.scope != TEAM for rule in chosen) else (None, [])
    errors = [error for error in errors + layer_errors if f"error:{error}" not in seen]
    if not chosen and not errors:
        return Result(None, None, "no rule due")
    output: dict[str, object] = {}
    if chosen:
        context = injection(chosen, touch.relative, touch.slug or touch.repo.name, layer)
        output["hookSpecificOutput"] = {"hookEventName": "PostToolUse", "additionalContext": context}
    if errors:
        output["systemMessage"] = "asdlc load_rules could not read a rule, so it was not delivered: " + "; ".join(errors)
    delivered = [str(rule.path) for rule in chosen] + [f"error:{error}" for error in errors]
    try:
        _update_state(state, lambda old: old | {key: sorted(set(old.get(key, [])) | set(delivered))})
    except OSError as error:
        print(f"asdlc: {HOOK} could not record what it delivered, so it may deliver it again: {error}", file=sys.stderr)
    names = ", ".join(str(rule.path.relative_to(touch.board)) for rule in chosen) or "no rules"
    reason = f"delivered {names} for {touch.relative} in {touch.repo}" + (f"; could not read: {'; '.join(errors)}" if errors else "")
    return Result(output, Verdict.ERROR if errors else Verdict.ALLOW, reason)


def on_session_start(payload: Mapping[str, object], environ: Mapping[str, str]) -> Result:
    source = str(payload.get("source") or "")
    if source not in RESET_SOURCES:
        return Result(None, None, f"nothing to forget on {source or 'this'} start")
    path = state_file(payload, environ)
    if source == "startup":
        _prune(path.parent, time.time())
    if path.exists():
        _update_state(path, lambda old: forget(old, source))
    return Result(None, None, f"forgot delivered rules on {source}")


def main() -> int:
    payload = json.load(sys.stdin)
    match payload.get("hook_event_name"):
        case "SessionStart":
            result = on_session_start(payload, os.environ)
        case "PostToolUse":
            result = on_tool_use(payload, os.environ)
        case _:
            result = Result(None, None, "not an event this hook handles")
    if result.verdict is not None:
        project = project_dir(payload)
        record(project, decision(datetime.now(), HOOK, str(payload.get("tool_name", "")), result.verdict, result.reason, current_branch(project)))
    if result.output:
        print(json.dumps(result.output))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as error:  # a broken loader must be visible, never block the tool call
        message = f"failed, so no rules were delivered: {type(error).__name__}: {error}"
        print(f"asdlc: {HOOK} {message}", file=sys.stderr)
        print(json.dumps({"systemMessage": f"asdlc {HOOK} {message}"}))
        record(project_dir({}), decision(datetime.now(), HOOK, "", Verdict.ERROR, message, ""))
        code = 0
    raise SystemExit(code)
