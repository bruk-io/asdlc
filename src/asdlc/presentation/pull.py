"""What asdlc writes on a task's pull request."""

from asdlc.domain import scaffold
from asdlc.domain.documents import Kind, qualify
from asdlc.domain.tasks import Task


def title(task: Task) -> str:
    """Give the title of a task's pull request."""
    return f"Task: {task.title}"


def description(task: Task) -> str:
    """Word the description of the draft pull request a start opens.

    It names the task's `task.md` and each requirement the task delivers.
    """
    document = scaffold.path(Kind.TASK, task.slug, task.name)
    delivered = "\n".join(f"- {qualify(task.slug, ref)}" for ref in task.delivers)
    parts = [
        f"Builds `{document}`.",
        f"Delivers:\n\n{delivered}" if delivered else "",
        "`asdlc task start` opened this as a draft before any work was done.",
    ]
    return "\n\n".join(part for part in parts if part) + "\n"
