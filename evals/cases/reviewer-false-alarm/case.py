"""Reviewer false alarm: the clean twin of the recall case is passed with no Important finding."""

import asdlc_eval as ev
import checks
import fixtures


def build(fixture: ev.Fixture) -> dict[str, object]:
    team, review = fixtures.review_scene(fixture, defect=False)
    return team.facts(review=review, review_prompt=fixtures.reviewer_prompt(review))


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    fixtures.reference_review(script, dict(facts["review"]), "clean", "important=0,nit=0",
                              "No findings: only failures are counted, both criteria are tested, and the recorded check ran on the last commit.",
                              policies=())
    return "clean"


def passed_clean(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    task = found.final.item("TASK-1")
    counts = checks.findings_of(task) if task else None
    if task and "review-passed" in task.labels and counts and counts[0] == 0 and task.status == "In Review":
        return True, f"passed clean with {counts[1]} nit(s)"
    return False, f"labels {task.labels if task else '-'}, status {task.status if task else '-'}, findings {counts}: {checks.last_review(task)[-300:] if task else ''!r}"
