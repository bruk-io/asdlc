import unittest

from tests.support import ROOT, load, run_script

artefacts = load("scripts/artefacts.py")

INTENT = """# Intent: a thing

- Author: Someone
- Status: draft.

## Problem

It hurts.

## Proposed outcome

- It stops hurting.

## Affected users and systems

- Everyone.

## Constraints

- None.

## Open questions

- [ ] First?
- [x] Second?
"""

SPEC = """# Spec: a thing

- Intent: [`intent/a.md`](../intent/a.md), accepted 2026-10-20
- Status: draft.

## Requirements

- **R1.** One.
- **R2. Named.** Two.

## Design

This answers intent question 1.

## Areas of concern

- None.

## Out of scope

Nothing.
"""

PLAN = """# Plan: a change

- Spec: [`spec/a.md`](../spec/a.md), approved 2026-10-20
- Status: draft.
- Delivers: R1, R2

## Files that change

| File | New |
|---|---|
| `a.py` | yes |

## Order of work

1. Do it.

## Risks

- **It breaks.** Unlikely.

## Proof

- It runs.
"""


def clean() -> dict[str, str]:
    return {"intent/a.md": INTENT, "spec/a.md": SPEC, "plan/a.md": PLAN}


def without_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    start = lines.index(f"## {heading}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[:start] + lines[end:])


class CleanArtefactsTest(unittest.TestCase):
    def test_a_well_formed_set_has_no_findings(self) -> None:
        self.assertEqual(artefacts.check_all(clean()), [])

    def test_this_repository_is_clean(self) -> None:
        done = run_script("scripts/artefacts.py", str(ROOT))
        self.assertEqual(done.returncode, 0, done.stdout)


class MissingSectionTest(unittest.TestCase):
    def assert_flags(self, path: str, heading: str) -> None:
        files = clean()
        files[path] = without_section(files[path], heading)
        findings = artefacts.check_all(files)
        self.assertTrue(
            any(f.path == path and f.rule == "section" and heading in f.message for f in findings),
            f"no finding for missing '{heading}' in {path}: {findings}",
        )

    def test_every_intent_section_is_required(self) -> None:
        for heading in artefacts.INTENT_SECTIONS:
            with self.subTest(heading=heading):
                self.assert_flags("intent/a.md", heading)

    def test_every_spec_section_is_required(self) -> None:
        for heading in artefacts.SPEC_SECTIONS:
            with self.subTest(heading=heading):
                self.assert_flags("spec/a.md", heading)

    def test_every_plan_section_is_required(self) -> None:
        for heading in artefacts.PLAN_SECTIONS:
            with self.subTest(heading=heading):
                self.assert_flags("plan/a.md", heading)


class LinkAndNumberingTest(unittest.TestCase):
    def rules(self, files: dict[str, str]) -> set[tuple[str, str]]:
        return {(f.path, f.rule) for f in artefacts.check_all(files)}

    def test_an_unsettled_open_question_is_flagged(self) -> None:
        files = clean()
        files["spec/a.md"] = SPEC.replace("intent question 1", "the first question")
        self.assertIn(("spec/a.md", "open-questions"), self.rules(files))

    def test_a_ticked_question_needs_no_answer(self) -> None:
        self.assertNotIn(("spec/a.md", "open-questions"), self.rules(clean()))

    def test_an_open_question_must_be_a_checkbox(self) -> None:
        files = clean()
        files["intent/a.md"] = INTENT.replace("- [ ] First?", "- First?")
        self.assertIn(("intent/a.md", "open-questions"), self.rules(files))

    def test_requirement_gaps_are_flagged(self) -> None:
        files = clean()
        files["spec/a.md"] = SPEC.replace("**R2. Named.**", "**R3. Named.**")
        self.assertIn(("spec/a.md", "requirements"), self.rules(files))

    def test_a_spec_must_link_an_existing_intent(self) -> None:
        files = clean()
        del files["intent/a.md"]
        self.assertIn(("spec/a.md", "intent-link"), self.rules(files))

    def test_a_plan_must_cite_requirements_that_exist(self) -> None:
        files = clean()
        files["plan/a.md"] = PLAN.replace("R1, R2", "R1, R9")
        self.assertIn(("plan/a.md", "delivers"), self.rules(files))

    def test_a_plan_must_link_an_existing_spec(self) -> None:
        files = clean()
        del files["spec/a.md"]
        self.assertIn(("plan/a.md", "spec-link"), self.rules(files))

    def test_supporting_documents_in_spec_are_not_specs(self) -> None:
        files = clean()
        files["spec/a-evals.md"] = "# Evals for a thing\n\nTables.\n"
        self.assertEqual(artefacts.check_all(files), [])


class ClaudeMdTest(unittest.TestCase):
    def test_a_long_claude_md_is_flagged(self) -> None:
        text = "line\n" * (artefacts.CLAUDE_MD_MAX_LINES + 1)
        self.assertEqual([f.rule for f in artefacts.check_all({"CLAUDE.md": text})], ["length"])

    def test_a_page_is_fine(self) -> None:
        text = "line\n" * artefacts.CLAUDE_MD_MAX_LINES
        self.assertEqual(artefacts.check_all({"CLAUDE.md": text}), [])


if __name__ == "__main__":
    unittest.main()
