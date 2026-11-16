import pytest

from asdlc.domain import documents
from asdlc.domain.documents import Kind, Mark

SPEC = """---
kind: spec
policies: [pii-in-logs, api-versioning]
---
# Spec: claims status

### R1: A customer can see their claim's status
- area: status

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
            {"area": "status"},
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
    ],
)
def test_what_is_wrong_inside_one_document(path, text, rule):
    assert rules(documents.parse(path, text)[1]) == [rule]


def test_state_cannot_be_written_into_a_document():
    """Status is worked out, so neither frontmatter nor a requirement can hold it."""
    text = "---\nkind: spec\nstatus: approved\n---\n### R1: a\n- state: built\n"
    assert rules(documents.parse(SPEC_PATH, text)[1]) == ["frontmatter", "property"]


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
