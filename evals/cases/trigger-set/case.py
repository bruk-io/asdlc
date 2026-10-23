"""The trigger set: does each request load capture-intent or orchestrate when it should, and stay quiet when it shouldn't?"""

from pathlib import Path

import asdlc_eval as ev
import fixtures

HERE = Path(__file__).parent


def build(fixture: ev.Fixture) -> dict[str, object]:
    team = fixtures.team(fixture, agent="kyle", items=[fixtures.COUNT_TASK], devs={"kyle": "name: kyle\nworkers: 2\nreview: true\n"},
                         publish=False)
    return team.facts()


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    case = ev.parse_case((HERE / "case.toml").read_text(), HERE.name)
    expect = case.items[session].expect
    if expect != "none":
        script.skill(f"asdlc:{expect}")
    return ""


def confusion(found: ev.Outcome, case: ev.Case, skill: str) -> tuple[list[int], list[int]]:
    """The items that loaded the skill without wanting it, and those that wanted it and didn't, numbered from 1."""
    false_positive, false_negative = [], []
    for number, item in enumerate(case.items):
        loaded = skill in ev.skills_loaded(e for e in found.events if e.session == number)
        wanted = item.expect == skill
        if loaded and not wanted:
            false_positive.append(number + 1)
        if wanted and not loaded:
            false_negative.append(number + 1)
    return false_positive, false_negative


def _verdict(found: ev.Outcome, case: ev.Case, skill: str) -> tuple[bool, str]:
    fp, fn = confusion(found, case, skill)
    should = sum(1 for i in case.items if i.expect == skill)
    detail = f"{skill}: {len(fp)} false positives of {len(case.items) - should} (items {fp}), {len(fn)} false negatives of {should} (items {fn})"
    return not fp and not fn, detail


def capture_intent_triggers(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    return _verdict(found, case, "capture-intent")


def orchestrate_triggers(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    return _verdict(found, case, "orchestrate")
