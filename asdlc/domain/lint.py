"""What is wrong between documents, and the library that holds them all."""

from collections.abc import Iterable, Sequence

from asdlc.domain.documents import (
    Document,
    Finding,
    Kind,
    Mark,
    label,
    listed,
    of_kind,
    parse,
    qualify,
    step_delivers,
)
from asdlc.domain.requirements import requirements

_ANSWERS = ("answered", "carried")


def lint(documents: Sequence[Document]) -> tuple[Finding, ...]:
    """Find a broken chain, a citation of nothing, and work that nothing delivers."""
    findings: list[Finding] = []
    intents = {d.slug: d for d in of_kind(documents, Kind.INTENT)}
    specs = {d.slug: d for d in of_kind(documents, Kind.SPEC)}
    plans = {d.slug: d for d in of_kind(documents, Kind.PLAN)}
    task_plans = of_kind(documents, Kind.PLAN, own_plan=True)
    tasks = of_kind(documents, Kind.TASK)
    known = {r.id: r for r in requirements(documents)}

    def wrong(document: Document, rule: str, message: str) -> None:
        findings.append(Finding(document.path, rule, message))

    for spec in specs.values():
        if spec.slug not in intents:
            wrong(spec, "chain", "a spec needs its intent.md beside it")
    for plan in plans.values():
        if plan.slug not in specs:
            wrong(plan, "chain", "a plan needs its spec.md beside it")
    for intent in intents.values():
        parent = intent.meta.get("parent")
        if parent is not None and parent not in intents:
            wrong(intent, "parent", f"parent '{parent}' is not an intent here")

    replacers: dict[str, list[str]] = {}
    for spec in specs.values():
        for item in spec.items:
            if item.mark is Mark.REQUIREMENT and "replaces" in item.props:
                target = qualify(spec.slug, item.props["replaces"])
                replacers.setdefault(target, []).append(label(item))
                if target not in known:
                    wrong(
                        spec,
                        "replaces",
                        f"{label(item)} replaces {target}, which no spec has",
                    )
        for ref in listed(spec, "retires"):
            if qualify(spec.slug, ref) not in known:
                target = qualify(spec.slug, ref)
                wrong(spec, "retires", f"retires {target}, which no spec has")
    for target, by in replacers.items():
        owner = specs.get(target.split(".")[0])
        if owner is None or target not in known:
            continue
        if len(by) > 1:
            wrong(
                owner,
                "replaces",
                f"{target} is replaced {len(by)} times; one requirement replaces "
                "it, and a later one replaces that",
            )
        if known[target].retired_by:
            wrong(owner, "replaces", f"{target} is both replaced and retired")

    for intent in intents.values():
        spec = specs.get(intent.slug)
        if spec is None:
            continue
        answers = {
            item.number: item.props.get("answer")
            for item in spec.items
            if item.mark is Mark.QUESTION
        }
        for question in intent.items:
            if answers.get(question.number) not in _ANSWERS:
                name = label(question)
                wrong(
                    spec,
                    "questions",
                    f"the intent's {name} must appear here as '### {name}: ...' "
                    "with '- answer: answered' or '- answer: carried'",
                )

    for plan in (*plans.values(), *task_plans):
        for step in plan.items:
            for ref in step_delivers(plan, step):
                if ref not in known:
                    wrong(
                        plan,
                        "delivers",
                        f"{label(step)} delivers {ref}, which no spec has",
                    )
            child = step.props.get("intent")
            if child is None:
                continue
            if child not in intents or intents[child].meta.get("parent") != plan.slug:
                wrong(
                    plan,
                    "child",
                    f"{label(step)} hands over to intent '{child}', which must "
                    f"exist and name '{plan.slug}' as its parent",
                )
    for plan in task_plans:
        if not any(t.slug == plan.slug and t.task == plan.task for t in tasks):
            wrong(plan, "chain", "a task's plan needs its task.md beside it")

    for task in tasks:
        plan = plans.get(task.slug)
        siblings = {t.task for t in tasks if t.slug == task.slug}
        step = task.meta.get("step")
        if plan is None:
            wrong(task, "chain", "a task needs the intent's plan.md to be cut from")
        elif step not in {str(item.number) for item in plan.items}:
            wrong(task, "step", f"step '{step}' is not a step of {plan.path}")
        for ref in listed(task, "delivers"):
            if qualify(task.slug, ref) not in known:
                target = qualify(task.slug, ref)
                wrong(task, "delivers", f"delivers {target}, which no spec has")
        for other in listed(task, "depends"):
            if other not in siblings or other == task.task:
                wrong(
                    task,
                    "depends",
                    f"depends on '{other}', which is not another task of this intent",
                )

    for plan in plans.values():
        planned = {ref for step in plan.items for ref in step_delivers(plan, step)}
        for id in known:
            if id.split(".")[0] == plan.slug and id not in planned:
                wrong(plan, "coverage", f"no step delivers {id}")
        mine = [task for task in tasks if task.slug == plan.slug]
        if not mine:
            continue
        cut = {task.meta.get("step") for task in mine}
        for step in plan.items:
            if str(step.number) not in cut and "intent" not in step.props:
                wrong(
                    plan,
                    "coverage",
                    f"no task was cut from {label(step)}, and it hands over to no "
                    "child intent",
                )
    return tuple(findings)


def library(
    texts: Iterable[tuple[str, str]],
) -> tuple[tuple[Document, ...], tuple[Finding, ...]]:
    """Build every document from `(path, text)` pairs, with everything wrong.

    The findings are those inside each document, then those between them.
    """
    documents = []
    findings: list[Finding] = []
    for path, text in texts:
        document, problems = parse(path, text)
        findings += problems
        if document is not None:
            documents.append(document)
    return tuple(documents), (*findings, *lint(documents))
