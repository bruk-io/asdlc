"""A new document's first text: a template's body under filled-in frontmatter."""

import re
from collections.abc import Mapping, Sequence

from asdlc.domain.documents import Kind, frontmatter

_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
_HEADING = re.compile(r"^# .*$", re.MULTILINE)
_KINDS = {
    Kind.INTENT: "Intent",
    Kind.SPEC: "Spec",
    Kind.PLAN: "Plan",
    Kind.TASK: "Task",
}


def well_named(name: str) -> bool:
    """Say whether a slug or a task folder is lowercase words joined by hyphens."""
    return _NAME.fullmatch(name) is not None


def _value(value: str | Sequence[str]) -> str:
    return value if isinstance(value, str) else f"[{', '.join(value)}]"


def document(
    kind: Kind,
    template: str,
    fields: Mapping[str, str | Sequence[str]],
    title: str = "",
) -> str:
    """Write a document's starting text.

    The frontmatter is built from `fields`, in the order given, so nothing in it
    is left for a model to get wrong. The body is the template's, with its
    heading replaced by `title` when one is given.
    """
    _, body, _ = frontmatter(template)
    lines = [
        f"kind: {kind}",
        *(f"{key}: {_value(value)}" for key, value in fields.items()),
    ]
    if title:
        body = _HEADING.sub(f"# {_KINDS[kind]}: {title}", body, count=1)
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def path(kind: Kind, slug: str, task: str | None = None) -> str:
    """Give the path, from the repository root, of the document of a kind."""
    folder = f"intent/{slug}" if task is None else f"intent/{slug}/tasks/{task}"
    return f"{folder}/{kind}.md"
