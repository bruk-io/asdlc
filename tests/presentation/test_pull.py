from dataclasses import replace

from asdlc.domain.tasks import State, Task
from asdlc.presentation import pull

TASK = Task(
    id="claims/02-panel",
    slug="claims",
    name="02-panel",
    title="the status panel",
    step="2",
    size="5",
    delivers=("R1", "R3", "notices.R2"),
    depends=("claims/01-endpoint",),
    branch="task/claims/02-panel",
    has_plan=False,
    state=State.READY,
)


def test_a_tasks_pull_request_is_titled_for_the_task():
    assert pull.title(TASK) == "Task: the status panel"


def test_the_description_names_the_tasks_document_and_each_requirement_in_full():
    assert pull.description(TASK) == (
        "Builds `intent/claims/tasks/02-panel/task.md`.\n"
        "\n"
        "Delivers:\n"
        "\n"
        "- claims.R1\n"
        "- claims.R3\n"
        "- notices.R2\n"
        "\n"
        "`asdlc task start` opened this as a draft before any work was done.\n"
    )


def test_a_task_that_delivers_nothing_has_no_list():
    described = pull.description(replace(TASK, delivers=()))
    assert "Delivers" not in described
    assert described.startswith("Builds `intent/claims/tasks/02-panel/task.md`.\n\n`")
