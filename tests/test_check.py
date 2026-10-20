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


if __name__ == "__main__":
    unittest.main()
