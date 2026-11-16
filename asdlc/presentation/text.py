"""What a person or a script reads on stdout: one record per line, tab-separated.

No header and no alignment, so the bytes are the same piped or not.
"""

from collections.abc import Sequence

from asdlc.domain.documents import Finding
from asdlc.domain.guard import Ruling
from asdlc.domain.requirements import Requirement, Standing


def state(requirement: Requirement) -> str:
    """Say where a requirement stands in one word or two."""
    if requirement.standing is Standing.IN_FORCE:
        return requirement.progress
    return requirement.standing


def finding_line(finding: Finding) -> str:
    return f"{finding.path}\t{finding.rule}\t{finding.message}"


def requirement_line(requirement: Requirement) -> str:
    r = requirement
    return f"{r.id}\t{state(r)}\t{r.area}\t{r.title}"


def ruling_line(ruling: Ruling) -> str:
    return f"{ruling.verdict}\t{ruling.path}\t{ruling.reason}"


def requirement_record(requirement: Requirement, chain: Sequence[Requirement]) -> str:
    """Give one requirement in full: a field per line, then its lineage oldest first."""
    r = requirement
    fields = [
        ("id", r.id),
        ("title", r.title),
        ("area", r.area),
        ("state", state(r)),
        ("replaces", r.replaces or ""),
        ("replaced-by", r.replaced_by or ""),
        ("retired-by", r.retired_by or ""),
        *(("step", step) for step in r.steps),
        *(("task", task) for task in r.tasks),
        *(("lineage", link.id) for link in chain),
    ]
    return "\n".join(f"{name}\t{value}" for name, value in fields)


def error(message: str) -> str:
    return f"Error: {message}"
