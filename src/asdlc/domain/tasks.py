"""Tasks and intents as they stand now, worked out from documents and from git.

Nothing here is stored. A task is claimed because its branch exists, in review
because that branch has an open pull request that is not a draft, and done
because it was merged.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from asdlc.domain.documents import Document, Kind, listed, of_kind


class State(StrEnum):
    WAITING = "waiting"  # a task it depends on is not done
    READY = "ready"
    CLAIMED = "claimed"
    IN_REVIEW = "in review"
    DONE = "done"


class Stage(StrEnum):
    """How far an intent has got: the last document it has, then its tasks."""

    INTENT = "intent"
    SPEC = "spec"
    PLAN = "plan"
    TASKS = "tasks"
    BUILT = "built"


@dataclass(frozen=True)
class Task:
    id: str  # <slug>/<task>
    slug: str
    name: str
    title: str
    step: str
    size: str
    delivers: tuple[str, ...]
    depends: tuple[str, ...]  # task ids
    branch: str
    has_plan: bool
    state: State
    pull_request: str = ""  # the link of its open pull request; empty with none


@dataclass(frozen=True)
class Intent:
    slug: str
    title: str
    author: str
    parent: str
    stage: Stage
    tasks: tuple[Task, ...]


_MERGES = (
    re.compile(r"Merge pull request #\d+ from [^/\s]+/(\S+)"),
    re.compile(r"Merge branch '([^']+)'"),
)


def merged_branches(subjects: Iterable[str]) -> frozenset[str]:
    """Read the branches merged into main from its merge commits' subjects."""
    found = set()
    for subject in subjects:
        for pattern in _MERGES:
            if match := pattern.match(subject):
                found.add(match[1])
    return frozenset(found)


def branch_of(task_id: str) -> str:
    return f"task/{task_id}"


def _state(
    branch: str,
    blocked: bool,
    branches: frozenset[str],
    open_pulls: frozenset[str],
    merged: frozenset[str],
) -> State:
    if branch in merged:
        return State.DONE
    if branch in open_pulls:
        return State.IN_REVIEW
    if branch in branches:
        return State.CLAIMED
    return State.WAITING if blocked else State.READY


def tasks(
    documents: Sequence[Document],
    *,
    branches: frozenset[str] = frozenset(),
    open_pulls: frozenset[str] = frozenset(),
    merged: frozenset[str] = frozenset(),
    links: Mapping[str, str] | None = None,
) -> tuple[Task, ...]:
    """List every task with its state and the link of its pull request.

    `branches` are the branches that exist, `open_pulls` those with an open pull
    request that is not a draft, and `merged` those merged into main. `links`
    gives the link of each branch's open pull request, draft or not. The caller
    reads all four from git and from GitHub.
    """
    links = links or {}
    own_plans = {(d.slug, d.task) for d in of_kind(documents, Kind.PLAN, own_plan=True)}
    found = []
    for document in of_kind(documents, Kind.TASK):
        id = f"{document.slug}/{document.task}"
        depends = tuple(
            f"{document.slug}/{name}" for name in listed(document, "depends")
        )
        blocked = any(branch_of(other) not in merged for other in depends)
        size = document.meta.get("size", "")
        step = document.meta.get("step", "")
        found.append(
            Task(
                id=id,
                slug=document.slug,
                name=document.task or "",
                title=document.title,
                step=step if isinstance(step, str) else "",
                size=size if isinstance(size, str) else "",
                delivers=listed(document, "delivers"),
                depends=depends,
                branch=branch_of(id),
                has_plan=(document.slug, document.task) in own_plans,
                state=_state(branch_of(id), blocked, branches, open_pulls, merged),
                pull_request=links.get(branch_of(id), ""),
            )
        )
    return tuple(found)


def done(known: Iterable[Task]) -> frozenset[str]:
    """Give the ids of the tasks that are merged."""
    return frozenset(task.id for task in known if task.state is State.DONE)


def _stage(kinds: set[Kind], mine: Sequence[Task]) -> Stage:
    if mine and all(task.state is State.DONE for task in mine):
        return Stage.BUILT
    if mine:
        return Stage.TASKS
    if Kind.PLAN in kinds:
        return Stage.PLAN
    return Stage.SPEC if Kind.SPEC in kinds else Stage.INTENT


def intents(documents: Sequence[Document], known: Sequence[Task]) -> tuple[Intent, ...]:
    """List every intent with how far it has got and the tasks under it."""
    found = []
    for document in of_kind(documents, Kind.INTENT):
        kinds = {
            d.kind for d in documents if d.slug == document.slug and d.task is None
        }
        mine = tuple(task for task in known if task.slug == document.slug)
        author = document.meta.get("author", "")
        parent = document.meta.get("parent", "")
        found.append(
            Intent(
                slug=document.slug,
                title=document.title,
                author=author if isinstance(author, str) else "",
                parent=parent if isinstance(parent, str) else "",
                stage=_stage(kinds, mine),
                tasks=mine,
            )
        )
    return tuple(found)
