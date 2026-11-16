import pytest

from asdlc.domain.guard import Verdict, guard, prerequisite, rule, waiting

ON_MAIN = frozenset(
    {
        "intent/claims/intent.md",
        "intent/claims/spec.md",
        "intent/claims/plan.md",
        "intent/claims/tasks/01-endpoint/task.md",
        "intent/claims/tasks/02-panel/task.md",
        "intent/small/intent.md",
        "intent/small/spec.md",
    }
)
TASK = "task/claims/01-endpoint"


def verdict(branch: str, path: str) -> Verdict:
    return rule(branch, path, ON_MAIN).verdict


@pytest.mark.parametrize(
    ("branch", "own"),
    [
        ("intent/new", "intent/new/intent.md"),
        ("spec/small", "intent/small/spec.md"),
        ("plan/small", "intent/small/plan.md"),
        ("tasks/claims", "intent/claims/tasks/03-nav/task.md"),
    ],
)
def test_a_branch_that_adds_a_document_changes_only_that_document(branch, own):
    assert verdict(branch, own) is Verdict.ALLOW
    for other in (
        "src/app.py",
        "README.md",
        "intent/claims/spec.md",
        "intent/new/spec.md",
    ):
        assert verdict(branch, other) is Verdict.DENY, other


@pytest.mark.parametrize(
    ("branch", "own"),
    [
        ("spec/new", "intent/new/spec.md"),
        ("plan/new", "intent/new/plan.md"),
        ("tasks/small", "intent/small/tasks/01-a/task.md"),
        ("task/claims/03-nav", "src/nav.py"),
        ("change/new", "src/app.py"),
    ],
)
def test_a_document_waits_for_the_one_before_it_to_be_on_main(branch, own):
    ruling = rule(branch, own, ON_MAIN)
    assert ruling.verdict is Verdict.DENY
    assert "is not on main yet. Merging it is the approval" in ruling.reason


@pytest.mark.parametrize(
    "path",
    [
        "src/status.py",
        "tests/test_status.py",
        "intent/claims/tasks/01-endpoint/plan.md",
    ],
)
def test_a_task_builds_code_and_writes_its_own_plan(path):
    assert verdict(TASK, path) is Verdict.ALLOW


@pytest.mark.parametrize(
    "path", ["intent/claims/plan.md", "intent/claims/tasks/01-endpoint/task.md"]
)
def test_a_task_changing_accepted_work_is_marked(path):
    ruling = rule(TASK, path, ON_MAIN)
    assert ruling.verdict is Verdict.MARK
    assert "say why" in ruling.reason


@pytest.mark.parametrize(
    "path",
    [
        "intent/claims/spec.md",
        "intent/claims/intent.md",
        "intent/claims/tasks/02-panel/task.md",
        "intent/small/spec.md",
    ],
)
def test_a_task_cannot_change_another_document(path):
    assert verdict(TASK, path) is Verdict.DENY


def test_a_small_intent_is_built_in_one_branch_with_its_plan():
    assert verdict("change/small", "intent/small/plan.md") is Verdict.ALLOW
    assert verdict("change/small", "src/app.py") is Verdict.ALLOW
    assert verdict("change/small", "intent/small/spec.md") is Verdict.DENY


def test_any_other_branch_leaves_documents_alone():
    assert verdict("fix-typo", "src/app.py") is Verdict.ALLOW
    ruling = rule("fix-typo", "intent/claims/spec.md", ON_MAIN)
    assert ruling.verdict is Verdict.DENY
    assert "intent/<slug>, spec/<slug>, plan/<slug> or tasks/<slug>" in ruling.reason


def test_a_repository_with_no_documents_on_main_is_not_guarded():
    assert (
        rule("anything", "intent/first/intent.md", frozenset()).verdict is Verdict.ALLOW
    )


def test_guard_returns_only_what_is_not_freely_allowed():
    paths = ["src/a.py", "intent/claims/plan.md", "intent/claims/spec.md"]
    assert [(r.path, r.verdict) for r in guard(TASK, paths, ON_MAIN)] == [
        ("intent/claims/plan.md", Verdict.MARK),
        ("intent/claims/spec.md", Verdict.DENY),
    ]


@pytest.mark.parametrize(
    ("branch", "needs"),
    [
        ("intent/new", None),
        ("spec/new", "intent/new/intent.md"),
        ("plan/new", "intent/new/spec.md"),
        ("tasks/new", "intent/new/plan.md"),
        ("task/new/01-a", "intent/new/tasks/01-a/task.md"),
        ("change/new", "intent/new/spec.md"),
        ("fix-typo", None),
    ],
)
def test_what_a_branch_waits_for(branch, needs):
    assert prerequisite(branch) == needs


def test_a_branch_can_start_once_what_it_waits_for_is_on_main():
    assert waiting("plan/small", ON_MAIN) is None
    assert waiting("intent/anything", frozenset()) is None
    reason = waiting("plan/new", ON_MAIN)
    assert reason.startswith("intent/new/spec.md is not on main yet.")
