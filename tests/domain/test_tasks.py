import pytest

from asdlc.domain.lint import library
from asdlc.domain.tasks import Stage, State, done, intents, merged_branches, tasks

INTENT = "---\nkind: intent\nauthor: a\n---\n# Intent: claims status\n"
SPEC = "---\nkind: spec\n---\n# Spec: claims status\n### R1: one\n### R2: two\n"
PLAN = (
    "---\nkind: plan\n---\n# Plan: claims status\n"
    "### Step 1: x\n- delivers: R1\n### Step 2: y\n- delivers: R2\n"
)
FIRST = "---\nkind: task\nstep: 1\ndelivers: [R1]\nsize: 3\n---\n# Task: the endpoint\n"
SECOND = (
    "---\nkind: task\nstep: 2\ndelivers: [R2]\ndepends: [01-a]\n---\n"
    "# Task: the panel\n"
)
FILES = {
    "intent/claims/intent.md": INTENT,
    "intent/claims/spec.md": SPEC,
    "intent/claims/plan.md": PLAN,
    "intent/claims/tasks/01-a/task.md": FIRST,
    "intent/claims/tasks/02-b/task.md": SECOND,
    "intent/claims/tasks/02-b/plan.md": "---\nkind: plan\n---\n### Step 1: z\n",
}


def documents(*paths: str):
    found, findings = library((path, FILES[path]) for path in paths or FILES)
    assert findings == ()
    return found


def states(**facts: frozenset[str]) -> dict[str, State]:
    return {task.name: task.state for task in tasks(documents(), **facts)}


@pytest.mark.parametrize(
    ("subject", "branch"),
    [
        ("Merge pull request #12 from bruk-io/task/claims/01-a", "task/claims/01-a"),
        ("Merge pull request #3 from someone/spec/claims", "spec/claims"),
        ("Merge branch 'task/claims/02-b'", "task/claims/02-b"),
    ],
)
def test_a_merge_commit_names_the_branch_it_merged(subject, branch):
    assert merged_branches([subject]) == {branch}


def test_other_subjects_name_no_branch():
    subjects = ["Add the endpoint", "Merge remote-tracking branch 'origin/main'", ""]
    assert merged_branches(subjects) == frozenset()


def test_a_task_carries_what_its_document_declares():
    first, second = tasks(documents())
    assert (first.id, first.title, first.step, first.size) == (
        "claims/01-a",
        "the endpoint",
        "1",
        "3",
    )
    assert (first.delivers, first.branch, first.has_plan) == (
        ("R1",),
        "task/claims/01-a",
        False,
    )
    assert (second.depends, second.has_plan) == (("claims/01-a",), True)


def test_a_task_waits_for_what_it_depends_on():
    assert states() == {"01-a": State.READY, "02-b": State.WAITING}
    merged = frozenset({"task/claims/01-a"})
    assert states(merged=merged) == {"01-a": State.DONE, "02-b": State.READY}


def test_a_branch_claims_a_pull_request_reviews_a_merge_finishes():
    branch = frozenset({"task/claims/01-a"})
    assert states(branches=branch)["01-a"] is State.CLAIMED
    assert states(branches=branch, open_pulls=branch)["01-a"] is State.IN_REVIEW
    assert (
        states(branches=branch, open_pulls=branch, merged=branch)["01-a"] is State.DONE
    )


def test_a_claimed_task_is_claimed_even_while_it_waits():
    assert states(branches=frozenset({"task/claims/02-b"}))["02-b"] is State.CLAIMED


def test_done_is_the_ids_of_merged_tasks():
    merged = frozenset({"task/claims/01-a", "spec/claims"})
    assert done(tasks(documents(), merged=merged)) == {"claims/01-a"}


@pytest.mark.parametrize(
    ("paths", "merged", "stage"),
    [
        (["intent/claims/intent.md"], [], Stage.INTENT),
        (["intent/claims/intent.md", "intent/claims/spec.md"], [], Stage.SPEC),
        (list(FILES)[:3], [], Stage.PLAN),
        (list(FILES), [], Stage.TASKS),
        (list(FILES), ["task/claims/01-a"], Stage.TASKS),
        (list(FILES), ["task/claims/01-a", "task/claims/02-b"], Stage.BUILT),
    ],
)
def test_an_intent_is_as_far_as_its_last_document_then_its_tasks(paths, merged, stage):
    found = documents(*paths)
    (intent,) = intents(found, tasks(found, merged=frozenset(merged)))
    assert (intent.slug, intent.title, intent.author, intent.stage) == (
        "claims",
        "claims status",
        "a",
        stage,
    )
