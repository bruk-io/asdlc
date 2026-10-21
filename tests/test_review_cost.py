import json
import tempfile
import unittest
from pathlib import Path

from tests.support import load, run_script

review_cost = load("scripts/review_cost.py")

RESULT = {
    "type": "result",
    "subtype": "success",
    "duration_ms": 412000,
    "num_turns": 23,
    "total_cost_usd": 1.23456,
    "modelUsage": {
        "claude-opus-5-5": {"inputTokens": 1200, "outputTokens": 3400, "cacheReadInputTokens": 50000, "cacheCreationInputTokens": 9000, "costUSD": 1.1},
        "claude-haiku-5-5": {"inputTokens": 800, "outputTokens": 90, "costUSD": 0.13456},
    },
}


class SummariseTest(unittest.TestCase):
    def test_reports_totals_and_each_model(self) -> None:
        text = review_cost.summarise([{"type": "system"}, RESULT])
        self.assertIn("$1.2346", text)
        self.assertIn("412s", text)
        self.assertIn("Turns: 23", text)
        self.assertIn("| claude-opus-5-5 | 1200 | 3400 | 50000 | 9000 | $1.1000 |", text)
        self.assertIn("| claude-haiku-5-5 | 800 | 90 | 0 | 0 | $0.1346 |", text)

    def test_uses_the_last_result(self) -> None:
        earlier = {**RESULT, "total_cost_usd": 9.0}
        self.assertIn("$1.2346", review_cost.summarise([earlier, RESULT]))

    def test_shows_why_a_failed_run_failed(self) -> None:
        failed = {**RESULT, "is_error": True, "result": "Invalid bearer token", "total_cost_usd": 0, "modelUsage": {}}
        self.assertIn("The run ended in an error: Invalid bearer token", review_cost.summarise([failed]))

    def test_falls_back_to_the_errors_list_and_shortens_long_text(self) -> None:
        failed = {**RESULT, "is_error": True, "errors": ["x" * 900]}
        line = next(l for l in review_cost.summarise([failed]).splitlines() if "ended in an error" in l)
        self.assertTrue(line.endswith("..."))
        self.assertLess(len(line), 600)

    def test_a_successful_run_mentions_no_error(self) -> None:
        self.assertNotIn("error", review_cost.summarise([RESULT]))

    def test_says_so_when_there_is_no_result(self) -> None:
        self.assertIn("unknown", review_cost.summarise([{"type": "system"}]))


class ScriptTest(unittest.TestCase):
    def test_reads_an_execution_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.json"
            path.write_text(json.dumps([RESULT]))
            done = run_script("scripts/review_cost.py", str(path))
        self.assertEqual(done.returncode, 0)
        self.assertIn("claude-opus-5-5", done.stdout)

    def test_a_missing_file_never_fails_the_job(self) -> None:
        for args in ((), ("",), ("/nonexistent/out.json",)):
            with self.subTest(args=args):
                done = run_script("scripts/review_cost.py", *args)
                self.assertEqual(done.returncode, 0)
                self.assertIn("unknown", done.stdout)


if __name__ == "__main__":
    unittest.main()
