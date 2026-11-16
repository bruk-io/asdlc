"""The `--json` shapes. Full identifiers, and fields are only ever added."""

from collections.abc import Sequence

from asdlc.domain.documents import Finding
from asdlc.domain.guard import Ruling
from asdlc.domain.requirements import Requirement
from asdlc.presentation.text import state


def finding(found: Finding) -> dict[str, str]:
    return {"path": found.path, "rule": found.rule, "message": found.message}


def ruling(found: Ruling) -> dict[str, str]:
    return {"path": found.path, "verdict": found.verdict, "reason": found.reason}


def requirement(found: Requirement) -> dict[str, object]:
    return {
        "id": found.id,
        "title": found.title,
        "area": found.area,
        "state": state(found),
        "standing": found.standing,
        "progress": found.progress,
        "replaces": found.replaces,
        "replaced_by": found.replaced_by,
        "retired_by": found.retired_by,
        "steps": list(found.steps),
        "tasks": list(found.tasks),
    }


def requirement_in_full(
    found: Requirement, chain: Sequence[Requirement]
) -> dict[str, object]:
    return requirement(found) | {"lineage": [link.id for link in chain]}
