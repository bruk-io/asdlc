import pytest

from asdlc.domain import documents
from asdlc.domain.documents import Kind, Mark

SPEC = """---
kind: spec
policies: [pii-in-logs, api-versioning]
---
# Spec: claims status

### R1: A customer can see their claim's status

Detail that is not a property.

### R2: Status updates within 2 seconds
- replaces: other.R3
"""


def rules(findings):
    return [finding.rule for finding in findings]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("intent/claims/intent.md", (Kind.INTENT, "claims", None)),
        ("intent/claims/spec.md", (Kind.SPEC, "claims", None)),
        ("intent/claims/plan.md", (Kind.PLAN, "claims", None)),
        ("intent/claims/tasks/01-a/task.md", (Kind.TASK, "claims", "01-a")),
        ("intent/claims/tasks/01-a/plan.md", (Kind.PLAN, "claims", "01-a")),
    ],
)
def test_a_path_says_what_a_document_is(path, expected):
    assert documents.place(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "intent/claims.md",
        "intent/claims/notes.md",
        "intent/claims/tasks/task.md",
        "spec/claims.md",
        "intent/a/b/intent.md",
    ],
)
def test_any_other_path_is_not_a_document(path):
    assert documents.place(path) is None


def test_frontmatter_is_flat_keys_with_a_value_or_an_inline_list():
    text = "---\nkind: task\nstep: 2\ndelivers: [R1, R4]\ndepends: []\n---\n# Task\n"
    meta, body, problems = documents.frontmatter(text)
    assert meta == {
        "kind": "task",
        "step": "2",
        "delivers": ("R1", "R4"),
        "depends": (),
    }
    assert (body, problems) == ("# Task\n", ())


@pytest.mark.parametrize("text", ["# Intent\n", "---\nkind: intent\n# open\n", ""])
def test_a_file_without_frontmatter_says_so(text):
    assert len(documents.frontmatter(text)[2]) == 1


def test_nested_frontmatter_is_refused():
    text = "---\nkind: spec\npolicies:\n  - pii\nkind: spec\n---\n"
    assert len(documents.frontmatter(text)[2]) == 3


def test_a_spec_and_the_headings_others_cite():
    spec, findings = documents.parse("intent/claims/spec.md", SPEC)
    assert findings == ()
    assert (spec.kind, spec.slug) == (Kind.SPEC, "claims")
    assert spec.meta["policies"] == ("pii-in-logs", "api-versioning")
    assert [(i.mark, i.number, i.title, dict(i.props)) for i in spec.items] == [
        (
            Mark.REQUIREMENT,
            1,
            "A customer can see their claim's status",
            {},
        ),
        (
            Mark.REQUIREMENT,
            2,
            "Status updates within 2 seconds",
            {"replaces": "other.R3"},
        ),
    ]


def test_a_heading_inside_a_code_fence_is_not_an_item():
    text = "---\nkind: spec\n---\n```\n### R9: an example\n```\n### R1: the real one\n"
    spec, findings = documents.parse("intent/claims/spec.md", text)
    assert ([item.number for item in spec.items], findings) == ([1], ())


SPEC_PATH = "intent/claims/spec.md"
INTENT_PATH = "intent/claims/intent.md"
PLAN_PATH = "intent/claims/plan.md"


@pytest.mark.parametrize(
    ("path", "text", "rule"),
    [
        pytest.param(SPEC_PATH, "---\nkind: plan\n---\n", "kind", id="wrong-kind"),
        pytest.param(
            SPEC_PATH,
            "---\nkind: spec\nowner: x\n---\n",
            "frontmatter",
            id="unknown-key",
        ),
        pytest.param(
            INTENT_PATH, "---\nkind: intent\n---\n", "frontmatter", id="missing-key"
        ),
        pytest.param(
            INTENT_PATH,
            "---\nkind: intent\nauthor: [a, b]\n---\n",
            "frontmatter",
            id="list-for-one-value",
        ),
        pytest.param(
            SPEC_PATH,
            "---\nkind: spec\n---\n### R1: a\n### R3: c\n",
            "numbering",
            id="number-skipped",
        ),
        pytest.param(
            SPEC_PATH,
            "---\nkind: spec\n---\n### R1: a\n### R1: b\n",
            "numbering",
            id="number-repeated",
        ),
        pytest.param(
            INTENT_PATH,
            "---\nkind: intent\nauthor: a\n---\n### R1: a\n",
            "heading",
            id="heading-of-another-kind",
        ),
        pytest.param(
            SPEC_PATH,
            "---\nkind: spec\n---\n### R1 no colon\n",
            "heading",
            id="nearly-a-heading",
        ),
        pytest.param(
            SPEC_PATH,
            "---\nkind: spec\n---\n### R1: a\n- owner: x\n",
            "property",
            id="unknown-property",
        ),
        pytest.param(
            PLAN_PATH,
            "---\nkind: plan\n---\n## Risks\n- none\n",
            "files",
            id="no-files",
        ),
        pytest.param(
            PLAN_PATH,
            "---\nkind: plan\n---\n## Files that change\nThe usual ones.\n",
            "files",
            id="files-not-listed",
        ),
        pytest.param(
            PLAN_PATH,
            "---\nkind: plan\n---\n## Files that change\n- <a file this changes>\n",
            "files",
            id="files-left-as-the-template",
        ),
    ],
)
def test_what_is_wrong_inside_one_document(path, text, rule):
    assert rules(documents.parse(path, text)[1]) == [rule]


def test_a_plan_that_names_a_file_is_clean():
    text = "---\nkind: plan\n---\n## Files that change\n- api/status.py (new)\n"
    assert documents.parse(PLAN_PATH, text)[1] == ()


def test_a_body_splits_into_its_sections():
    fence = "```\n## not a heading\n```\n"
    body = f"# Plan: x\n## Files that change\n\n- a.py\n{fence}## Risks\nNone.\n"
    assert dict(documents.sections(body)) == {
        "Files that change": ("- a.py", "```", "## not a heading", "```"),
        "Risks": ("None.",),
    }


def test_list_items_are_read_whole_and_a_placeholder_is_not_an_entry():
    lines = ("Some prose.", "- one", "- two is", "  wrapped", "- <fill me in>")
    assert documents.bullets(lines) == ("one", "two is wrapped", "<fill me in>")
    assert documents.filled(documents.bullets(lines)) == ("one", "two is wrapped")


def test_a_tables_rows_are_its_cells_without_the_header():
    lines = ("| Constraint | Met by |", "| :--- | ---: |", "| a \\| b | R1 |", "prose")
    assert documents.table_rows(lines) == (("a | b", "R1"),)


def test_state_cannot_be_written_into_a_document():
    """Status is worked out, so neither frontmatter nor a requirement can hold it."""
    text = "---\nkind: spec\nstatus: approved\n---\n### R1: a\n- state: built\n"
    assert rules(documents.parse(SPEC_PATH, text)[1]) == ["frontmatter", "property"]


def test_a_requirement_no_longer_carries_an_area():
    text = "---\nkind: spec\n---\n### R1: a\n- area: status\n"
    assert rules(documents.parse(SPEC_PATH, text)[1]) == ["property"]


def test_a_property_written_twice_under_one_heading_is_a_finding():
    """The second line would win and the first be dropped, with nothing said."""
    text = (
        "---\nkind: spec\n---\n"
        "### R1: a\n- replaces: old.R1\n- replaces: old.R2\n- replaces: old.R3\n"
    )
    document, findings = documents.parse(SPEC_PATH, text)
    assert [(found.rule, found.message) for found in findings] == [
        (
            "property",
            "R1 has '- replaces:' more than once, and only the last would count. "
            "A heading takes a property once: to end two requirements, write a "
            "requirement for each",
        )
    ]
    assert document.items[0].repeated == ("replaces",)


def test_a_step_that_delivers_on_two_lines_is_told_to_use_one():
    text = (
        "---\nkind: plan\n---\n## Files that change\n\n- a.py\n\n"
        "### Step 1: a\n- delivers: R1\n- delivers: R2\n"
    )
    messages = [found.message for found in documents.parse(PLAN_PATH, text)[1]]
    assert messages == [
        "Step 1 has '- delivers:' more than once, and only the last would count. "
        "A heading takes a property once: list what a step delivers on one line, "
        "as 'R1, R2'"
    ]


def test_each_property_written_once_is_no_finding():
    spec = "---\nkind: spec\n---\n### R1: a\n- replaces: old.R1\n### R2: b\n"
    document, findings = documents.parse(SPEC_PATH, spec)
    assert findings == ()
    assert [item.repeated for item in document.items] == [(), ()]


def test_a_concern_with_no_owner_is_a_finding():
    text = "---\nkind: spec\n---\n### C1: nobody load tested the cache\n"
    findings = documents.parse(SPEC_PATH, text)[1]
    assert [(found.rule, found.message) for found in findings] == [
        (
            "owner",
            "C1 names no owner: put '- owner: <who decides>' on the line under its "
            "heading. A line lower down is not read as its owner",
        )
    ]


def test_an_owner_under_the_concerns_text_is_not_its_owner():
    text = (
        "---\nkind: spec\n---\n"
        "### C1: nobody load tested the cache\n\nIt may fall over.\n"
        "- owner: the claims team\n"
    )
    assert rules(documents.parse(SPEC_PATH, text)[1]) == ["owner"]


def test_a_concern_with_its_owner_under_the_heading_is_no_finding():
    text = (
        "---\nkind: spec\n---\n"
        "### C1: nobody load tested the cache\n- owner: the claims team\n\n"
        "It may fall over.\n"
    )
    assert documents.parse(SPEC_PATH, text)[1] == ()


def test_a_file_in_the_wrong_place_is_no_document():
    document, findings = documents.parse("intent/claims/notes.md", "anything")
    assert (document, rules(findings)) == (None, ["place"])


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("# Intent: claims status self-service\n", "claims status self-service"),
        ("\n# Task: the status panel\n## Done when\n", "the status panel"),
        ("# A heading with no kind\n", "A heading with no kind"),
        ("## Only a second-level heading\n", ""),
    ],
)
def test_a_documents_title_is_its_first_heading_without_its_kind(body, expected):
    assert documents.title(body) == expected
