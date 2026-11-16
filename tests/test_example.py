"""The domain over the worked example on disk: files in, requirements out."""

import pytest

from asdlc.domain.documents import Kind
from asdlc.domain.lint import library
from asdlc.domain.requirements import Progress, Standing, lineage, requirements
from asdlc.io.files import document_texts


@pytest.fixture
def documents(example):
    found, findings = library(document_texts(example))
    assert (len(found), findings) == (11, ())
    return found


def test_what_is_in_force_is_worked_out_from_every_spec(documents):
    known = {r.id: r for r in requirements(documents)}
    assert {id: r.standing for id, r in known.items()} == {
        "claims-status.R1": Standing.IN_FORCE,
        "claims-status.R2": Standing.REPLACED,
        "claims-status.R3": Standing.REPLACED,
        "claims-status.R4": Standing.IN_FORCE,
        "live-status.R1": Standing.IN_FORCE,
        "live-status.R2": Standing.IN_FORCE,
        "claim-states.R1": Standing.IN_FORCE,
    }
    assert known["claims-status.R3"].replaced_by == "live-status.R1"


def test_progress_follows_the_plan_the_tasks_and_what_has_merged(documents):
    known = {r.id: r for r in requirements(documents)}
    assert known["live-status.R1"].progress is Progress.APPROVED
    assert known["claims-status.R1"].progress is Progress.IN_TASKS
    assert known["claims-status.R1"].tasks == (
        "claims-status/01-status-endpoint",
        "claims-status/02-status-panel",
    )
    done = frozenset({"claims-status/01-status-endpoint"})
    half = {r.id: r.progress for r in requirements(documents, done)}
    assert half["claims-status.R4"] is Progress.BUILT
    assert half["claims-status.R1"] is Progress.IN_TASKS


def test_a_requirement_with_a_plan_and_no_tasks_is_planned(documents):
    no_tasks = tuple(d for d in documents if d.kind is not Kind.TASK)
    progress = {r.id: r.progress for r in requirements(no_tasks)}
    assert progress["claims-status.R4"] is Progress.PLANNED


@pytest.mark.parametrize("id", ["claims-status.R3", "live-status.R1"])
def test_lineage_is_the_whole_chain_from_any_member(documents, id):
    chain = lineage(requirements(documents), id)
    assert [r.id for r in chain] == ["claims-status.R3", "live-status.R1"]


def test_lineage_of_something_never_replaced_or_unknown(documents):
    known = requirements(documents)
    assert [r.id for r in lineage(known, "claims-status.R1")] == ["claims-status.R1"]
    assert lineage(known, "claims-status.R9") == ()
