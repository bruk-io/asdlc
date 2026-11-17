"""What a person or a script reads on stdout: one record per line, tab-separated.

No header and no alignment, so the bytes are the same piped or not.
"""

from collections.abc import Sequence

from asdlc.domain.documents import Finding
from asdlc.domain.guard import Ruling
from asdlc.domain.requirements import Requirement, Standing
from asdlc.domain.tasks import Intent, Task


def state(requirement: Requirement) -> str:
    """Say where a requirement stands in one word or two."""
    if requirement.standing is Standing.IN_FORCE:
        return requirement.progress
    return requirement.standing


def finding_line(finding: Finding) -> str:
    return f"{finding.path}\t{finding.rule}\t{finding.message}"


def requirement_line(requirement: Requirement) -> str:
    r = requirement
    return f"{r.id}\t{state(r)}\t{r.title}"


def ruling_line(ruling: Ruling) -> str:
    return f"{ruling.verdict}\t{ruling.path}\t{ruling.reason}"


def requirement_record(requirement: Requirement, chain: Sequence[Requirement]) -> str:
    """Give one requirement in full: a field per line, then its lineage oldest first."""
    r = requirement
    fields = [
        ("id", r.id),
        ("title", r.title),
        ("state", state(r)),
        ("replaces", r.replaces or ""),
        ("replaced-by", r.replaced_by or ""),
        ("retired-by", r.retired_by or ""),
        *(("step", step) for step in r.steps),
        *(("task", task) for task in r.tasks),
        *(("lineage", link.id) for link in chain),
    ]
    return "\n".join(f"{name}\t{value}" for name, value in fields)


def task_line(task: Task) -> str:
    return f"{task.id}\t{task.state}\t{task.size}\t{task.step}\t{task.title}"


def task_record(task: Task) -> str:
    """Give one task in full: a field per line."""
    fields = [
        ("id", task.id),
        ("title", task.title),
        ("state", task.state),
        ("step", task.step),
        ("size", task.size),
        ("branch", task.branch),
        ("own-plan", "yes" if task.has_plan else "no"),
        *(("delivers", ref) for ref in task.delivers),
        *(("depends", other) for other in task.depends),
    ]
    return "\n".join(f"{name}\t{value}" for name, value in fields)


def intent_line(intent: Intent) -> str:
    return f"{intent.slug}\t{intent.stage}\t{intent.parent}\t{intent.title}"


def intent_record(intent: Intent) -> str:
    """Give one intent in full: a field per line, then a line per task."""
    fields = [
        ("slug", intent.slug),
        ("title", intent.title),
        ("author", intent.author),
        ("parent", intent.parent),
        ("stage", intent.stage),
        *(("task", f"{task.id}\t{task.state}") for task in intent.tasks),
    ]
    return "\n".join(f"{name}\t{value}" for name, value in fields)


def error(message: str) -> str:
    return f"Error: {message}"
