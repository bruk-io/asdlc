"""Requirements as they stand now, worked out from every spec, plan and task."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from asdlc.domain.documents import (
    Document,
    Kind,
    Mark,
    label,
    listed,
    of_kind,
    qualify,
    step_delivers,
)


class Standing(StrEnum):
    IN_FORCE = "in force"
    REPLACED = "replaced"
    RETIRED = "retired"


class Progress(StrEnum):
    APPROVED = "approved"
    PLANNED = "planned"
    IN_TASKS = "in tasks"
    BUILT = "built"


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    replaces: str | None
    replaced_by: str | None
    retired_by: str | None  # the slug of the intent whose spec retired it
    steps: tuple[str, ...]
    tasks: tuple[str, ...]
    standing: Standing
    progress: Progress


def _standing(id: str, replaced: dict[str, str], retired: dict[str, str]) -> Standing:
    if id in replaced:
        return Standing.REPLACED
    if id in retired:
        return Standing.RETIRED
    return Standing.IN_FORCE


def _progress(tasks: Sequence[str], planned: bool, done: frozenset[str]) -> Progress:
    if tasks and all(task in done for task in tasks):
        return Progress.BUILT
    if tasks:
        return Progress.IN_TASKS
    return Progress.PLANNED if planned else Progress.APPROVED


def requirements(
    documents: Sequence[Document], done: frozenset[str] = frozenset()
) -> tuple[Requirement, ...]:
    """List every requirement in every spec, with what replaced it and how far it got.

    `done` is the tasks already merged, as `<slug>/<task>`. Git knows that, so the
    caller supplies it.
    """
    specs = of_kind(documents, Kind.SPEC)
    replaced = {
        qualify(spec.slug, item.props["replaces"]): qualify(spec.slug, label(item))
        for spec in specs
        for item in spec.items
        if item.mark is Mark.REQUIREMENT and "replaces" in item.props
    }
    retired = {
        qualify(spec.slug, ref): spec.slug
        for spec in specs
        for ref in listed(spec, "retires")
    }
    steps: dict[str, list[str]] = {}
    for plan in of_kind(documents, Kind.PLAN):
        for step in plan.items:
            for ref in step_delivers(plan, step):
                steps.setdefault(ref, []).append(f"{plan.slug} / {label(step)}")
    tasks: dict[str, list[str]] = {}
    for task in of_kind(documents, Kind.TASK):
        for ref in listed(task, "delivers"):
            name = f"{task.slug}/{task.task}"
            tasks.setdefault(qualify(task.slug, ref), []).append(name)
    found = []
    for spec in specs:
        for item in spec.items:
            if item.mark is not Mark.REQUIREMENT:
                continue
            id = qualify(spec.slug, label(item))
            mine = tuple(tasks.get(id, ()))
            replaces = item.props.get("replaces")
            found.append(
                Requirement(
                    id=id,
                    title=item.title,
                    replaces=qualify(spec.slug, replaces) if replaces else None,
                    replaced_by=replaced.get(id),
                    retired_by=retired.get(id),
                    steps=tuple(steps.get(id, ())),
                    tasks=mine,
                    standing=_standing(id, replaced, retired),
                    progress=_progress(mine, id in steps, done),
                )
            )
    return tuple(found)


def lineage(known: Sequence[Requirement], id: str) -> tuple[Requirement, ...]:
    """Give the chain a requirement belongs to, oldest first.

    The chain is what it replaced, itself, then what replaced it. It is empty when
    no requirement has the id.
    """
    by_id = {requirement.id: requirement for requirement in known}
    if id not in by_id:
        return ()
    first = by_id[id]
    seen = {first.id}
    while first.replaces in by_id and first.replaces not in seen:
        first = by_id[first.replaces]
        seen.add(first.id)
    chain = [first]
    while chain[-1].replaced_by in by_id and len(chain) <= len(by_id):
        chain.append(by_id[chain[-1].replaced_by])
    return tuple(chain)
