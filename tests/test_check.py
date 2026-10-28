import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT


class PythonVersionTest(unittest.TestCase):
    def test_runs_on_the_declared_floor(self) -> None:
        self.assertGreaterEqual(sys.version_info[:2], (3, 15))


class CheckCommandTest(unittest.TestCase):
    """scripts/check, run against a copy of itself beside a failing artefact check."""

    def test_a_failing_step_fails_the_whole_check(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "scripts").mkdir()
            (root / "tests").mkdir()
            shutil.copy(ROOT / "scripts" / "check", root / "scripts" / "check")
            (root / "scripts" / "artefacts.py").write_text("raise SystemExit(1)\n")
            done = subprocess.run(
                [sys.executable, str(root / "scripts" / "check")], capture_output=True, text=True
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("artefacts: FAILED", done.stdout)


class GateReminderTest(unittest.TestCase):
    """scripts/check prints a reminder when the gate has no evidence, and never lets it change the exit code."""

    def make_root(self, folder: str, verifier_exit: int) -> Path:
        root = Path(folder)
        (root / "scripts").mkdir()
        (root / "tests").mkdir()
        shutil.copy(ROOT / "scripts" / "check", root / "scripts" / "check")
        (root / "scripts" / "artefacts.py").write_text("raise SystemExit(0)\n")
        (root / "scripts" / "eval").write_text("raise SystemExit(0)\n")
        (root / "tests" / "__init__.py").write_text("")
        (root / "tests" / "test_ok.py").write_text("import unittest\n\n\nclass T(unittest.TestCase):\n    def test_it(self) -> None:\n        pass\n")
        (root / "scripts" / "gate_evidence.py").write_text(
            f"import sys\nprint('gate evidence missing: no passing report')\nraise SystemExit({verifier_exit})\n")
        return root

    def run_check(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(root / "scripts" / "check")], capture_output=True, text=True)

    def test_a_missing_gate_is_reminded_and_the_check_still_passes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = self.run_check(self.make_root(folder, 1))
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertIn("reminder: gate evidence missing", done.stdout)
            self.assertIn("scripts/eval gate", done.stdout)

    def test_a_held_gate_says_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = self.run_check(self.make_root(folder, 0))
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertNotIn("reminder", done.stdout)

    def test_no_verifier_says_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder, 1)
            (root / "scripts" / "gate_evidence.py").unlink()
            done = self.run_check(root)
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertNotIn("reminder", done.stdout)


if __name__ == "__main__":
    unittest.main()
