"""The guard: which files a branch may change, given which documents are on main.

A document is accepted when it is on main, so a branch that builds on a document
waits for that document's merge, and a branch that adds a document changes nothing
else. The branch name says what a branch is for:

    intent/<slug>         adds intent/<slug>/intent.md
    spec/<slug>           adds spec.md; the intent must be on main
    plan/<slug>           adds plan.md; the spec must be on main
    tasks/<slug>          adds the task.md files; the plan must be on main
    task/<slug>/<task>    builds one task; its task.md must be on main
    change/<slug>         builds a small intent, plan.md first; the spec must be on main

`prerequisite` says what a branch waits for, and is asked when the branch is made.
`rule` says whether a branch may change one file. It is asked before each push and
on the pull request, so the two cannot disagree.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Verdict(StrEnum):
    ALLOW = "allow"
    MARK = "mark"  # allowed, and shown at the merge as a change to accepted work
    DENY = "deny"


@dataclass(frozen=True)
class Ruling:
    path: str
    verdict: Verdict
    reason: str


_WAITS = "Merging it is the approval this branch waits for."


def _document(path: str) -> bool:
    return path.startswith("intent/")


def _allow(path: str) -> Ruling:
    return Ruling(path, Verdict.ALLOW, "")


def _deny(path: str, reason: str) -> Ruling:
    return Ruling(path, Verdict.DENY, reason)


def _adds(
    what: str,
    only: str,
    needs: str | None,
    path: str,
    on_main: frozenset[str],
    fits: bool,
) -> Ruling:
    if needs is not None and needs not in on_main:
        return _deny(path, f"{needs} is not on main yet. {_WAITS}")
    if not fits:
        return _deny(
            path,
            f"this branch adds {what}, so it changes only {only}: the merge then "
            "accepts exactly that and nothing else",
        )
    return _allow(path)


def prerequisite(branch: str) -> str | None:
    """Name the document that must be on main before this branch does any work.

    Return None for a branch that waits for nothing: an intent, or a branch the
    loop does not name.
    """
    match branch.split("/"):
        case ["spec", slug]:
            return f"intent/{slug}/intent.md"
        case ["plan", slug] | ["change", slug]:
            return f"intent/{slug}/spec.md"
        case ["tasks", slug]:
            return f"intent/{slug}/plan.md"
        case ["task", slug, task]:
            return f"intent/{slug}/tasks/{task}/task.md"
    return None


def waiting(branch: str, on_main: frozenset[str]) -> str | None:
    """Say why a branch cannot start yet; None when it can."""
    needs = prerequisite(branch)
    if needs is None or needs in on_main:
        return None
    return f"{needs} is not on main yet. {_WAITS}"


def rule(branch: str, path: str, on_main: frozenset[str]) -> Ruling:
    """Decide whether `branch` may change `path`, given the files on main.

    `path` is relative to the repository root.
    """
    match branch.split("/"):
        case ["intent", slug]:
            only = f"intent/{slug}/intent.md"
            return _adds("an intent", only, None, path, on_main, path == only)
        case ["spec", slug]:
            only = f"intent/{slug}/spec.md"
            needs = f"intent/{slug}/intent.md"
            return _adds("a spec", only, needs, path, on_main, path == only)
        case ["plan", slug]:
            only = f"intent/{slug}/plan.md"
            needs = f"intent/{slug}/spec.md"
            return _adds("a plan", only, needs, path, on_main, path == only)
        case ["tasks", slug]:
            only = f"intent/{slug}/tasks/<task>/task.md"
            needs = f"intent/{slug}/plan.md"
            pattern = rf"intent/{re.escape(slug)}/tasks/[^/]+/task\.md"
            fits = re.fullmatch(pattern, path) is not None
            return _adds("an intent's tasks", only, needs, path, on_main, fits)
        case ["task", slug, task]:
            folder = f"intent/{slug}/tasks/{task}/"
            if f"{folder}task.md" not in on_main:
                return _deny(path, f"{folder}task.md is not on main yet. {_WAITS}")
            if not _document(path) or path == f"{folder}plan.md":
                return _allow(path)
            if path in (f"{folder}task.md", f"intent/{slug}/plan.md"):
                return Ruling(
                    path,
                    Verdict.MARK,
                    f"{path} is accepted work, and this task is changing it. That "
                    "is allowed and counted: say why in the pull request",
                )
            return _deny(
                path,
                "a task changes its own plan and, when it must, its intent's plan. "
                f"{path} is another document, and changes on a branch of its own",
            )
        case ["change", slug]:
            needs = f"intent/{slug}/spec.md"
            if needs not in on_main:
                return _deny(path, f"{needs} is not on main yet. {_WAITS}")
            if not _document(path) or path == f"intent/{slug}/plan.md":
                return _allow(path)
            return _deny(
                path,
                f"a change adds its plan and its code. {path} is another document, "
                "and changes on a branch of its own",
            )
    if _document(path) and any(_document(known) for known in on_main):
        return _deny(
            path,
            "documents change on a branch named for what it adds: intent/<slug>, "
            f"spec/<slug>, plan/<slug> or tasks/<slug>. The branch '{branch}' is "
            "none of them",
        )
    return _allow(path)


def guard(
    branch: str, paths: Iterable[str], on_main: frozenset[str]
) -> tuple[Ruling, ...]:
    """List every path a branch should not change freely: the denials and the marks."""
    rulings = (rule(branch, path, on_main) for path in paths)
    return tuple(ruling for ruling in rulings if ruling.verdict is not Verdict.ALLOW)
