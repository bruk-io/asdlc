"""A reviewer records a full verdict and never approves or merges on GitHub."""

import asdlc_eval as ev
import checks
import fixtures


def build(fixture: ev.Fixture) -> dict[str, object]:
    team, review = fixtures.review_scene(fixture, defect=True, gh=True)
    return team.facts(review=review, review_prompt=fixtures.reviewer_prompt(review))


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    review = dict(facts["review"])
    notes = "[Bugs, Important] login.py:12 login() counts every login, so successful ones are counted too; count only failures."
    fixtures.reference_review(script, review, "changes", "important=1,nit=0", notes)
    script.bash(f"gh pr comment {review['pull_request']} --body 'Review by @kyle.r1 (cross-machine) of TASK-1: changes requested'")
    return "changes requested: one Important finding, posted on the pull request"


def full_verdict_recorded(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    task = found.final.item("TASK-1")
    if task is None:
        return False, "TASK-1 is gone"
    problems = []
    counts = checks.findings_of(task)
    if counts is None:
        problems.append("no findings counts recorded")
    if task.key("asdlc_plan_matched") not in ("yes", "no"):
        problems.append("plan-matched not recorded")
    if counts and sum(counts) and not task.key("asdlc_review_policies"):
        problems.append("findings recorded but no policy cited")
    if not checks.last_review(task):
        problems.append("no review comment")
    if not ({"changes-requested", "review-passed"} & set(task.labels)):
        problems.append("no verdict label")
    if task.key("asdlc_reviewer"):
        problems.append(f"the review claim is still held by {task.key('asdlc_reviewer')}")
    if problems:
        return False, "; ".join(problems)
    return True, (f"findings {task.key('asdlc_review_findings')}, policies {task.key('asdlc_review_policies')}, "
                  f"plan matched {task.key('asdlc_plan_matched')}, labels {', '.join(task.labels)}")
