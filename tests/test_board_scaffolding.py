import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests.support import ROOT, load, run_script

asdlc = load("scripts/asdlc")
load("hooks/decision_log.py")
rules = load("hooks/load_rules.py")

TEMPLATES = ROOT / "templates" / "board"
BACKLOG = os.environ.get("ASDLC_BACKLOG") or shutil.which("backlog")
needs_backlog = unittest.skipIf(BACKLOG is None and not os.environ.get("CI"), "the backlog CLI is not installed")
ISOLATED = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}
SCAFFOLDING = (
    ".claude-plugin/marketplace.json",
    ".gitignore",
    "asdlc.toml",
    "devs/README.md",
    "devs/example.yaml",
    "plugins/team/.claude-plugin/plugin.json",
    "plugins/team/README.md",
    "plugins/team/review.md",
    "plugins/team/rules/testing-python.md",
    "plugins/team/rules/testing.md",
    "plugins/team/skills/testing/SKILL.md",
    "plugins/team/skills/writing-a-contract/SKILL.md",
    "plugins/team/templates/contract.md",
)


def _validator() -> list[str] | None:
    """`claude plugin validate`: the installed CLI, or in CI the published one through npx."""
    if found := shutil.which("claude"):
        return [found]
    if os.environ.get("CI") and (npx := shutil.which("npx")):
        return [npx, "--yes", "@anthropic-ai/claude-code"]
    return None


VALIDATOR = _validator()


# --- the logic -------------------------------------------------------------------------


class ScaffoldingLogicTest(unittest.TestCase):
    def test_marketplace_name_comes_from_the_folder(self) -> None:
        for folder, expected in (("team-board", "team-board"), ("Team Board", "team-board"), ("acme_tasks.git", "acme-tasks-git"), ("...", "tasks")):
            with self.subTest(folder=folder):
                self.assertEqual(asdlc.marketplace_name(folder), expected)

    def test_missing_scaffolding_never_includes_an_existing_file(self) -> None:
        templates = {"a.json": '{"name": "{{marketplace}}"}', "b/c.md": "c", "d.md": "d"}
        added = asdlc.missing_scaffolding(templates, ["b/c.md"], "team-board")
        self.assertEqual(added, {"a.json": '{"name": "team-board"}', "d.md": "d"})
        self.assertEqual(asdlc.missing_scaffolding(templates, list(templates), "x"), {})


class TemplatesTest(unittest.TestCase):
    """The scaffolding as shipped: every file present, each in the shape its reader needs."""

    def test_every_file_is_there_and_nothing_else(self) -> None:
        shipped = sorted(p.relative_to(TEMPLATES).as_posix() for p in TEMPLATES.rglob("*") if p.is_file())
        self.assertEqual(shipped, sorted(SCAFFOLDING))

    def test_the_team_review_policy_judges_team_code_not_asdlcs_own(self) -> None:
        """I3: reviewers judge a team's code by the team's policy in the tasks repository, never by asdlc's own REVIEW.md."""
        policy = (TEMPLATES / "plugins" / "team" / "review.md").read_text()
        for needed in ("Bugs", "Security", "Compliance", "Important", "Nit", "at most five nits", "acceptance criteria", "contract",
                       "size-1: plan approval skipped", "plugins/<repo-slug>/review.md"):
            with self.subTest(needed=needed):
                self.assertIn(needed, policy)
        for asdlc_only in ("Python 3.15", "plan/<slug>.md", "R21", "R23", "./scripts/check"):
            with self.subTest(asdlc_only=asdlc_only):
                self.assertNotIn(asdlc_only, policy)
        reviewer = (ROOT / "agents" / "reviewer.md").read_text()
        self.assertNotIn("CLAUDE_PLUGIN_ROOT}/REVIEW.md", reviewer)
        self.assertIn("policies", reviewer)

    def test_the_marketplace_lists_the_team_plugin(self) -> None:
        market = json.loads((TEMPLATES / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(market["name"], asdlc.MARKETPLACE_PLACEHOLDER)
        self.assertTrue(market["owner"]["name"])
        self.assertEqual([(p["name"], p["source"]) for p in market["plugins"]], [("team", "./plugins/team")])
        plugin = json.loads((TEMPLATES / "plugins" / "team" / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(plugin["name"], "team")
        self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(plugin["description"] and plugin["author"]["name"])

    def test_each_skill_has_a_name_matching_its_folder_and_a_description(self) -> None:
        for skill in sorted((TEMPLATES / "plugins" / "team" / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=skill.parent.name):
                fields = asdlc.frontmatter(skill.read_text())
                self.assertEqual(fields["name"], skill.parent.name)
                self.assertGreater(len(fields["description"]), 100)

    def test_the_testing_rules_match_tests_in_each_language_and_not_other_code(self) -> None:
        folder = TEMPLATES / "plugins" / "team" / "rules"
        neutral = rules.parse_rule(folder / "testing.md", "team", (folder / "testing.md").read_text())
        python = rules.parse_rule(folder / "testing-python.md", "team", (folder / "testing-python.md").read_text())
        for path in ("tests/test_a.py", "pkg/tests/unit/a.py", "src/a_test.go", "conftest.py", "Tests/AppTests/LoginTests.swift",
                     "App/LoginTests.swift", "app/src/test/kotlin/LoginTest.kt", "app/src/androidTest/java/a/B.kt",
                     "src/login.test.ts", "web/src/__tests__/a.tsx", "src/login.spec.tsx"):
            with self.subTest(path=path):
                self.assertTrue(rules.matches(path, neutral.paths))
        for path in ("src/app.py", "App/Login.swift", "app/src/main/kotlin/Login.kt", "src/login.ts", "README.md", "src/testing.ts"):
            with self.subTest(path=path, expected="miss"):
                self.assertFalse(rules.matches(path, neutral.paths))
        self.assertTrue(rules.matches("tests/unit/test_a.py", python.paths))
        self.assertFalse(rules.matches("src/login.test.ts", python.paths))
        self.assertFalse(rules.matches("src/app.py", python.paths))

    def test_settings_parse_and_say_what_they_do(self) -> None:
        text = (TEMPLATES / "asdlc.toml").read_text()
        self.assertEqual(tomllib.loads(text), {"stale_after": "2h", "review_fallback_after": "30m"})
        for key in ("stale_after", "review_fallback_after"):
            before = text.split(f"\n{key} =")[0].rstrip().splitlines()[-1]
            self.assertTrue(before.startswith("#"), f"{key} has no comment saying what it does")

    def test_the_example_preferences_are_the_flat_subset(self) -> None:
        lines = [line for line in (TEMPLATES / "devs" / "example.yaml").read_text().splitlines() if line.strip() and not line.startswith("#")]
        keys = [re.match(r"^([a-z]+): \S", line).group(1) for line in lines]
        self.assertEqual(keys, ["name", "prefer", "avoid", "workers", "review"])

    def test_house_style(self) -> None:
        for path in sorted(TEMPLATES.rglob("*")) + [ROOT / "docs" / "repo-plugins.md"]:
            if path.is_file():
                with self.subTest(path=path.relative_to(ROOT).as_posix()):
                    text = path.read_text()
                    self.assertNotIn("—", text, "regular hyphens, never em dashes")
                    self.assertNotRegex(text.lower(), r"\b(color|behavior|organization|center)\b", "Canadian spelling")


# --- init-board, against real repositories --------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, **ISOLATED})
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


def _init_board(board: Path) -> subprocess.CompletedProcess[str]:
    return run_script("scripts/asdlc", "init-board", str(board), env={**ISOLATED, "ASDLC_BACKLOG": BACKLOG or "backlog"})


@needs_backlog
class InitBoardScaffoldingTest(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.board = Path(handle.name).resolve() / "Acme Tasks"

    def test_a_fresh_board_gets_everything_in_one_commit(self) -> None:
        done = _init_board(self.board)
        self.assertEqual(done.returncode, 0, done.stderr)
        for path in SCAFFOLDING:
            self.assertTrue((self.board / path).is_file(), path)
        self.assertEqual(json.loads((self.board / ".claude-plugin" / "marketplace.json").read_text())["name"], "acme-tasks")
        self.assertEqual((self.board / "plugins" / "team" / "rules" / "testing.md").read_text(),
                         (TEMPLATES / "plugins" / "team" / "rules" / "testing.md").read_text())
        self.assertEqual(_git(self.board, "log", "--format=%s"), "Initialise the asdlc board")
        self.assertEqual(_git(self.board, "status", "--porcelain"), "")
        self.assertIn("/plugin install team --marketplace", done.stdout)

    def test_an_existing_board_gets_only_what_is_missing(self) -> None:
        self.assertEqual(_init_board(self.board).returncode, 0)
        edited = self.board / "plugins" / "team" / "rules" / "testing.md"
        edited.write_text("# Our own testing rule\n")
        (self.board / "devs" / "README.md").unlink()
        (self.board / "asdlc.toml").write_text('stale_after = "4h"\n')
        _git(self.board, "add", "-A")
        _git(self.board, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Our changes")
        (self.board / "notes.txt").write_text("staged, not ours to commit\n")
        _git(self.board, "add", "notes.txt")

        done = _init_board(self.board)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("added 1 scaffolding file(s)", done.stderr)
        self.assertEqual(edited.read_text(), "# Our own testing rule\n")
        self.assertEqual((self.board / "asdlc.toml").read_text(), 'stale_after = "4h"\n')
        self.assertEqual((self.board / "devs" / "README.md").read_text(), (TEMPLATES / "devs" / "README.md").read_text())
        self.assertEqual(_git(self.board, "log", "-1", "--format=%s"), "Update the asdlc board's config and add missing scaffolding")
        self.assertEqual(_git(self.board, "show", "--name-only", "--format=", "HEAD"), "devs/README.md")
        self.assertEqual(_git(self.board, "status", "--porcelain"), "A  notes.txt")

        head = _git(self.board, "rev-parse", "HEAD")
        again = _init_board(self.board)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotIn("added", again.stderr)
        self.assertEqual(_git(self.board, "rev-parse", "HEAD"), head)

    def test_the_board_ignores_the_hook_decision_log(self) -> None:
        """M9: the hooks' decision log, .asdlc/, never shows up as a change in the tasks repository."""
        self.assertEqual(_init_board(self.board).returncode, 0)
        self.assertIn(".asdlc/", (self.board / ".gitignore").read_text().splitlines())
        (self.board / ".gitignore").write_text("node_modules/\n")
        _git(self.board, "-c", "commit.gpgsign=false", "commit", "-qam", "Our own ignores")
        done = _init_board(self.board)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((self.board / ".gitignore").read_text(), "node_modules/\n.asdlc/\n")
        (self.board / ".asdlc").mkdir()
        (self.board / ".asdlc" / "hooks.jsonl").write_text("{}\n")
        self.assertEqual(_git(self.board, "status", "--porcelain"), "")

    @unittest.skipIf(VALIDATOR is None, "claude is not installed, so the JSON shape tests above stand in for plugin validate")
    def test_the_marketplace_and_team_plugin_validate(self) -> None:
        self.assertEqual(_init_board(self.board).returncode, 0)
        for folder in (self.board, self.board / "plugins" / "team"):
            with self.subTest(folder=folder.name):
                done = subprocess.run([*VALIDATOR, "plugin", "validate", str(folder)], capture_output=True, text=True, timeout=300)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertIn("Validation passed", done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
