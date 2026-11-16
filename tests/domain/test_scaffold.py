import pytest

from asdlc.domain import scaffold
from asdlc.domain.documents import Kind, parse

TEMPLATE = (
    "---\nkind: task\nstep: <n>\n---\n# Task: <what gets built>\n\n## Done when\n"
)


def test_frontmatter_is_built_from_the_fields_and_the_body_kept():
    fields = {"step": "2", "delivers": ("R1", "R4"), "size": "3"}
    text = scaffold.document(Kind.TASK, TEMPLATE, fields, "the status panel")
    assert text == (
        "---\nkind: task\nstep: 2\ndelivers: [R1, R4]\nsize: 3\n---\n"
        "# Task: the status panel\n\n## Done when\n"
    )
    document, findings = parse("intent/claims/tasks/02-panel/task.md", text)
    assert findings == ()
    assert (document.title, document.meta["delivers"]) == (
        "the status panel",
        ("R1", "R4"),
    )


def test_without_a_title_the_templates_heading_stays():
    text = scaffold.document(Kind.TASK, TEMPLATE, {"step": "1", "delivers": ("R1",)})
    assert "# Task: <what gets built>" in text


@pytest.mark.parametrize("name", ["claims-status", "01-status-endpoint", "a", "v2"])
def test_a_good_name(name):
    assert scaffold.well_named(name)


@pytest.mark.parametrize(
    "name", ["", "Claims", "claims status", "-claims", "a/b", "a.b"]
)
def test_a_bad_name(name):
    assert not scaffold.well_named(name)


def test_where_each_document_goes():
    assert scaffold.path(Kind.INTENT, "claims") == "intent/claims/intent.md"
    assert scaffold.path(Kind.PLAN, "claims") == "intent/claims/plan.md"
    assert (
        scaffold.path(Kind.TASK, "claims", "01-a") == "intent/claims/tasks/01-a/task.md"
    )
    assert (
        scaffold.path(Kind.PLAN, "claims", "01-a") == "intent/claims/tasks/01-a/plan.md"
    )
