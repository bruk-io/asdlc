from asdlc.domain.lint import library

INTENT = "---\nkind: intent\nauthor: a\n---\n"
SPEC = "---\nkind: spec\n---\n"
PLAN = "---\nkind: plan\n---\n"
BASE = {
    "intent/old/intent.md": INTENT,
    "intent/old/spec.md": SPEC + "### R1: one\n### R2: two\n",
}


def task(step: int, delivers: str, extra: str = "") -> str:
    return f"---\nkind: task\nstep: {step}\ndelivers: [{delivers}]\n{extra}---\n"


def found(**files: str) -> list[str]:
    """The rules broken by the base plus `files`, keyed by path with `__` for `/`."""
    texts = BASE | {
        f"intent/{key.replace('__', '/')}.md": text for key, text in files.items()
    }
    return [finding.rule for finding in library(texts.items())[1]]


def test_the_base_is_clean():
    assert found() == []


def test_a_document_needs_the_one_before_it():
    assert found(new__spec=SPEC) == ["chain"]
    assert found(new__intent=INTENT, new__plan=PLAN) == ["chain"]
    assert found(old__tasks__a__task=task(1, "R1")) == ["chain"]


def test_a_citation_must_point_at_something():
    replaces = SPEC + "### R1: x\n- replaces: old.R9\n"
    assert found(new__intent=INTENT, new__spec=replaces) == ["replaces"]
    retires = "---\nkind: spec\nretires: [old.R9]\n---\n"
    assert found(new__intent=INTENT, new__spec=retires) == ["retires"]
    orphan = "---\nkind: intent\nauthor: a\nparent: nobody\n---\n"
    assert found(new__intent=orphan) == ["parent"]
    plan = PLAN + "### Step 1: x\n- delivers: R1, R2, R9\n"
    assert found(old__plan=plan) == ["delivers"]


def test_a_requirement_ends_only_once():
    twice = SPEC + "### R1: x\n- replaces: old.R1\n### R2: y\n- replaces: old.R1\n"
    assert found(new__intent=INTENT, new__spec=twice) == ["replaces"]


def test_an_intents_question_is_answered_or_carried_in_its_spec():
    asked = INTENT + "### Q1: who?\n"
    assert found(new__intent=asked, new__spec=SPEC) == ["questions"]
    vague = SPEC + "### Q1: who?\n- answer: later\n"
    assert found(new__intent=asked, new__spec=vague) == ["questions"]
    carried = SPEC + "### Q1: who?\n- answer: carried\n"
    assert found(new__intent=asked, new__spec=carried) == []


def test_every_requirement_reaches_a_step_and_every_step_a_task():
    assert found(old__plan=PLAN + "### Step 1: x\n- delivers: R1\n") == ["coverage"]
    plan = PLAN + "### Step 1: x\n- delivers: R1\n### Step 2: y\n- delivers: R2\n"
    assert found(old__plan=plan, old__tasks__a__task=task(1, "R1")) == ["coverage"]


def test_a_task_cites_a_real_step_and_real_siblings():
    plan = PLAN + "### Step 1: x\n- delivers: R1, R2\n"
    good = task(1, "R1")
    assert found(
        old__plan=plan, old__tasks__a__task=good, old__tasks__b__task=task(4, "R2")
    ) == ["step"]
    lonely = task(1, "R1", "depends: [b]\n")
    assert found(old__plan=plan, old__tasks__a__task=lonely) == ["depends"]


def test_a_step_may_hand_over_to_a_child_intent():
    plan = PLAN + "### Step 1: x\n- delivers: R1, R2\n### Step 2: y\n- intent: child\n"
    files = {"old__plan": plan, "old__tasks__a__task": task(1, "R1")}
    assert found(**files) == ["child"]
    assert found(**files, child__intent=INTENT) == ["child"]
    child = "---\nkind: intent\nauthor: a\nparent: old\n---\n"
    assert found(**files, child__intent=child) == []
