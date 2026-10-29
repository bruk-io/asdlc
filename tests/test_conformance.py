import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, load, run_script

conformance = load("scripts/conformance.py")

SPEC = """# Spec: a thing

## Requirements

- **R1.** One.
- **R2. Two.** Two.
- **R3.** Three.
"""
EXISTING = {"skills/capture-intent/SKILL.md", "hooks/guard_board.py", "evals/cases/trigger-set/case.toml", "tests/test_hooks.py"}


def document(*lines: str, beyond: tuple[str, ...] = ("- R3: ours.",)) -> str:
    return "\n".join(["# Conformance", "", "## Play 1", "", *lines, "", "## Beyond the playbook", "", *beyond, ""])


GOOD = "- **P1.1** | A claim. | R1, R2 | built: skill:capture-intent, hook:guard_board.py | tested: eval:trigger-set, test:test_hooks.py"


def run(text: str) -> list[str]:
    return [str(f) for f in conformance.check(text, conformance.requirement_ids(SPEC), lambda path: path in EXISTING)]


class ParseTest(unittest.TestCase):
    def test_requirement_ids_read_both_spec_styles(self) -> None:
        self.assertEqual(conformance.requirement_ids(SPEC), ["R1", "R2", "R3"])

    def test_a_good_document_has_no_findings(self) -> None:
        self.assertEqual(run(document(GOOD)), [])

    def test_a_claim_line_that_cannot_be_read_is_reported_with_its_line(self) -> None:
        found = run(document("- **P1.1** | no fields"))
        self.assertTrue(any(f.startswith("line ") and "must read" in f for f in found), found)

    def test_a_none_field_takes_a_reason_and_no_targets(self) -> None:
        text = document("- **P1.1** | A claim. | R1, R2 | built: none: not built | tested: none: no eval yet, no hook either")
        self.assertEqual(run(text), [])


class FindingsTest(unittest.TestCase):
    def test_a_target_that_does_not_exist(self) -> None:
        found = run(document(GOOD.replace("skill:capture-intent", "skill:made-up")))
        self.assertEqual(len(found), 1)
        self.assertIn("P1.1: built: skill:made-up does not exist (looked for skills/made-up/SKILL.md)", found[0])

    def test_an_unknown_kind_of_target(self) -> None:
        found = run(document(GOOD.replace("hook:guard_board.py", "magic:guard_board.py")))
        self.assertTrue(any("not a kind of target" in f for f in found), found)

    def test_none_without_a_reason(self) -> None:
        found = run(document(GOOD.replace("tested: eval:trigger-set, test:test_hooks.py", "tested: none:")))
        self.assertTrue(any("needs a reason" in f for f in found), found)

    def test_a_repeated_claim_id(self) -> None:
        found = run(document(GOOD, GOOD))
        self.assertEqual([f for f in found if "repeated" in f], ["P1.1: repeated; each claim has its own id so a gap can be named"])

    def test_a_claim_citing_a_requirement_the_spec_lacks(self) -> None:
        found = run(document(GOOD.replace("R1, R2", "R1, R2, R9")))
        self.assertIn("P1.1: R9 is not a requirement of the spec", found)

    def test_a_requirement_serving_no_claim(self) -> None:
        found = run(document(GOOD, beyond=()))
        self.assertEqual(len(found), 1)
        self.assertIn("R3: serves no claim and is not listed under 'Beyond the playbook'", found[0])

    def test_a_requirement_both_served_and_beyond(self) -> None:
        found = run(document(GOOD, beyond=("- R3: ours.", "- R1: also ours.")))
        self.assertEqual(len(found), 1)
        self.assertIn("R1 also serves a claim", found[0])

    def test_a_beyond_entry_for_a_requirement_the_spec_lacks(self) -> None:
        found = run(document(GOOD, beyond=("- R3: ours.", "- R7: invented.")))
        self.assertIn("Beyond the playbook: R7 is not a requirement of the spec", found)

    def test_a_document_with_no_claims(self) -> None:
        found = run(document(beyond=("- R1: a.", "- R2: b.", "- R3: c.")))
        self.assertEqual(found, ["spec/playbook-conformance.md: has no claims"])


class RealRepositoryTest(unittest.TestCase):
    def test_this_repository_conforms(self) -> None:
        done = run_script("scripts/conformance.py", str(ROOT))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("conformance: all clean", done.stdout)

    def test_a_repository_without_the_file_has_nothing_to_check(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = run_script("scripts/conformance.py", folder)
            self.assertEqual(done.returncode, 0)
            self.assertIn("nothing to check", done.stdout)


if __name__ == "__main__":
    unittest.main()
