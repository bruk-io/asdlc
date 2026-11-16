import json

from asdlc.domain.documents import Finding
from asdlc.domain.guard import Ruling, Verdict
from asdlc.domain.requirements import Progress, Requirement, Standing
from asdlc.presentation import data, hook, output, text


def requirement(id: str, title: str, **changes: object) -> Requirement:
    fields = dict(
        id=id,
        title=title,
        area="status",
        replaces=None,
        replaced_by=None,
        retired_by=None,
        steps=(),
        tasks=(),
        standing=Standing.IN_FORCE,
        progress=Progress.APPROVED,
    )
    return Requirement(**(fields | changes))


OLD = requirement(
    "old.R3",
    "Refresh every 60 seconds",
    replaced_by="new.R1",
    standing=Standing.REPLACED,
    steps=("old / Step 2",),
    tasks=("old/02-panel",),
)
NEW = requirement(
    "new.R1", "Update within 2 seconds", replaces="old.R3", progress=Progress.IN_TASKS
)


def test_a_finding_is_path_rule_message():
    found = Finding("intent/a/spec.md", "kind", "must say 'kind: spec'")
    assert text.finding_line(found) == "intent/a/spec.md\tkind\tmust say 'kind: spec'"
    assert data.finding(found) == {
        "path": "intent/a/spec.md",
        "rule": "kind",
        "message": "must say 'kind: spec'",
    }


def test_a_requirement_is_id_state_area_title():
    assert (
        text.requirement_line(NEW)
        == "new.R1\tin tasks\tstatus\tUpdate within 2 seconds"
    )
    assert (
        text.requirement_line(OLD)
        == "old.R3\treplaced\tstatus\tRefresh every 60 seconds"
    )


def test_the_state_of_a_retired_requirement():
    gone = requirement(
        "old.R1", "Fax a copy", retired_by="paperless", standing=Standing.RETIRED
    )
    assert text.state(gone) == "retired"
    assert data.requirement(gone)["retired_by"] == "paperless"


def test_a_requirement_in_full_is_a_field_per_line_then_its_lineage():
    assert text.requirement_record(OLD, (OLD, NEW)).split("\n") == [
        "id\told.R3",
        "title\tRefresh every 60 seconds",
        "area\tstatus",
        "state\treplaced",
        "replaces\t",
        "replaced-by\tnew.R1",
        "retired-by\t",
        "step\told / Step 2",
        "task\told/02-panel",
        "lineage\told.R3",
        "lineage\tnew.R1",
    ]


def test_a_requirement_as_json_keeps_every_field_and_its_lineage():
    document = data.requirement_in_full(NEW, (OLD, NEW))
    assert document == {
        "id": "new.R1",
        "title": "Update within 2 seconds",
        "area": "status",
        "state": "in tasks",
        "standing": "in force",
        "progress": "in tasks",
        "replaces": "old.R3",
        "replaced_by": None,
        "retired_by": None,
        "steps": [],
        "tasks": [],
        "lineage": ["old.R3", "new.R1"],
    }
    json.dumps(document)


def test_a_ruling_is_verdict_path_reason():
    found = Ruling("intent/a/spec.md", Verdict.DENY, "another document")
    assert text.ruling_line(found) == "deny\tintent/a/spec.md\tanother document"
    assert data.ruling(found)["verdict"] == "deny"


def listing(records, **flags):
    return output.listing(
        records,
        line=text.requirement_line,
        identifier=lambda r: r.id,
        document=data.requirement,
        as_json=flags.get("as_json", False),
        quiet=flags.get("quiet", False),
    )


def test_a_listing_is_lines_or_identifiers_or_one_json_array():
    assert listing([OLD, NEW]).count("\n") == 1
    assert listing([OLD, NEW], quiet=True) == "old.R3\nnew.R1"
    assert [r["id"] for r in json.loads(listing([OLD, NEW], as_json=True))] == [
        "old.R3",
        "new.R1",
    ]
    assert json.loads(listing([OLD, NEW], as_json=True, quiet=True)) == [
        "old.R3",
        "new.R1",
    ]


def test_an_empty_listing_prints_nothing_and_is_an_empty_array_as_json():
    assert listing([]) == ""
    assert listing([], as_json=True) == "[]"


def test_a_single_record_is_in_full_or_its_identifier_or_one_json_object():
    def single(**flags):
        return output.single(
            text="in full",
            identifier="new.R1",
            document={"id": "new.R1"},
            as_json=flags.get("as_json", False),
            quiet=flags.get("quiet", False),
        )

    assert single() == "in full"
    assert single(quiet=True) == "new.R1"
    assert json.loads(single(as_json=True)) == {"id": "new.R1"}
    assert json.loads(single(as_json=True, quiet=True)) == "new.R1"


def test_an_error_leads_with_the_word():
    assert text.error("no branch 'x'") == "Error: no branch 'x'"


def test_a_push_denial_names_the_branch_and_each_file():
    denied = (Ruling("app.py", Verdict.DENY, "this branch adds a spec"),)
    output = json.loads(hook.push_denial("spec/claims", denied))["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "'spec/claims'" in output["permissionDecisionReason"]
    assert "- app.py: this branch adds a spec" in output["permissionDecisionReason"]


def test_lint_feedback_is_the_json_claude_code_reads_after_an_edit():
    found = (Finding("intent/a/spec.md", "kind", "must say 'kind: spec'"),)
    output = json.loads(hook.lint_feedback(found))["hookSpecificOutput"]
    assert output["hookEventName"] == "PostToolUse"
    assert (
        "- intent/a/spec.md: [kind] must say 'kind: spec'"
        in output["additionalContext"]
    )


def test_a_clean_document_gives_claude_nothing_to_read():
    assert hook.lint_feedback(()) == ""


def test_the_git_hook_runs_the_guard_and_is_recognised_as_ours():
    script = hook.git_hook("pre-push")
    assert script.startswith("#!/bin/sh\n")
    assert "exec asdlc branch check" in script
    assert "uv tool install" in script
    assert hook.ours(script)
    assert not hook.ours("#!/bin/sh\nnpm test\n")
