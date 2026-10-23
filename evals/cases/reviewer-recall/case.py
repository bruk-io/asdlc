"""Reviewer recall: a diff with one seeded defect is sent back with an Important finding naming it."""

import re

import asdlc_eval as ev
import checks
import fixtures

NAMES_IT = re.compile(r"succe(ss|ed)|every (login|attempt|call)|all logins|before (the )?check|regardless|unconditional", re.I)


def build(fixture: ev.Fixture) -> dict[str, object]:
    team, review = fixtures.review_scene(fixture, defect=True)
    return team.facts(review=review, review_prompt=fixtures.reviewer_prompt(review))


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    notes = ("[Bugs, Important] login.py:12 login() adds to FAILED before check(), so a successful login is counted too, "
             "against the acceptance criterion that successful logins leave FAILED unchanged; no test covers it.")
    fixtures.reference_review(script, dict(facts["review"]), "changes", "important=1,nit=0", notes)
    return "changes requested"


def sent_back_naming_the_defect(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    task = found.final.item("TASK-1")
    counts = checks.findings_of(task) if task else None
    review = checks.last_review(task) if task else ""
    if not task or "changes-requested" not in task.labels or not counts or counts[0] < 1:
        return False, f"not sent back with an Important finding (labels {task.labels if task else '-'}, findings {counts})"
    important = review.split("Nit")[0] if "Nit" in review else review
    if "login.py" not in review or not NAMES_IT.search(important):
        return False, f"sent back, but the findings don't name the defect: {review[-400:]!r}"
    return True, f"sent back with {counts[0]} Important finding(s) naming it"
