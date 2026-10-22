import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, load, run_script

load("hooks/decision_log.py")
rules = load("hooks/load_rules.py")

ISOLATED = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}
BOARD = Path("/board")


def rule(name: str, body: str = "Body.", scope: str = "team", paths: tuple[str, ...] = ()) -> object:
    folder = "team" if scope == "team" else scope
    return rules.Rule(BOARD / "plugins" / folder / "rules" / f"{name}.md", scope, paths, body)


# --- the logic -------------------------------------------------------------------------


class GlobTest(unittest.TestCase):
    def test_globs_are_relative_to_the_repository_root(self) -> None:
        cases = {
            "**/*.py": (["a.py", "src/a.py", "src/deep/er/a.py"], ["a.pyc", "a.py/x"]),
            "*.py": (["a.py"], ["src/a.py"]),
            "src/**": (["src/a", "src/a/b.ts"], ["lib/src/a", "srcx/a"]),
            "src/": (["src/a", "src/a/b"], ["lib/src/a"]),
            "./src/*.ts": (["src/a.ts"], ["src/x/a.ts"]),
            "/src/*.ts": (["src/a.ts"], ["lib/src/a.ts"]),
            "**/tests/**": (["tests/a.py", "pkg/tests/unit/a.py"], ["tests", "testsuite/a.py"]),
            "a?c.md": (["abc.md"], ["ac.md", "a/c.md"]),
            "**/*.{test,spec}.{ts,tsx}": (["a.test.ts", "src/b.spec.tsx"], ["a.ts", "a.test.js"]),
            "**/{test_*,*_test}.py": (["test_a.py", "x/a_test.py"], ["atest.py"]),
            "src/{core,{ui,app}/screens}/**": (["src/core/a", "src/ui/screens/a", "src/app/screens/b"], ["src/ui/a"]),
            "weird[1].md": (["weird[1].md"], ["weird1.md"]),
            "open{brace.md": (["open{brace.md"], ["openbrace.md"]),
        }
        for glob, (hits, misses) in cases.items():
            for path in hits:
                with self.subTest(glob=glob, path=path):
                    self.assertTrue(rules.matches(path, (glob,)))
            for path in misses:
                with self.subTest(glob=glob, path=path, expected="miss"):
                    self.assertFalse(rules.matches(path, (glob,)))

    def test_no_globs_matches_every_file(self) -> None:
        self.assertTrue(rules.matches("anything/at/all.swift", ()))

    def test_any_glob_in_the_list_is_enough(self) -> None:
        self.assertTrue(rules.matches("b/x.kt", ("a/**", "b/**")))


class ParseRuleTest(unittest.TestCase):
    path = Path("/board/plugins/team/rules/r.md")

    def parsed(self, text: str) -> object:
        return rules.parse_rule(self.path, "team", text)

    def test_block_list(self) -> None:
        found = self.parsed('---\ndescription: x\npaths:\n  - "**/*.py"\n  - \'src/**\'\n\n  - tests/**\nother: y\n---\n# Title\n\nBody\n')
        self.assertEqual(found.paths, ("**/*.py", "src/**", "tests/**"))
        self.assertEqual(found.body, "# Title\n\nBody")

    def test_flow_list_keeps_commas_inside_braces(self) -> None:
        found = self.parsed('---\npaths: ["**/*.{ts,tsx}", \'src/**\']\n---\nBody\n')
        self.assertEqual(found.paths, ("**/*.{ts,tsx}", "src/**"))

    def test_one_glob(self) -> None:
        self.assertEqual(self.parsed('---\npaths: "src/**"\n---\nBody\n').paths, ("src/**",))

    def test_no_paths_applies_everywhere(self) -> None:
        self.assertEqual(self.parsed("---\ndescription: x\n---\nBody\n").paths, ())
        plain = self.parsed("# No frontmatter\n\nBody\n")
        self.assertEqual((plain.paths, plain.body), ((), "# No frontmatter\n\nBody"))

    def test_refusals_say_what_to_fix(self) -> None:
        for text, says in (
            ("---\npaths:\n  - a/**\n# never closed\n", "never closed"),
            ("---\npaths:\n---\nBody\n", "lists no globs"),
            ("---\npaths: []\n---\nBody\n", "lists no globs"),
        ):
            with self.subTest(text=text):
                with self.assertRaisesRegex(rules.RuleError, says):
                    self.parsed(text)


class LayersTest(unittest.TestCase):
    text = '[layers.ui]\npaths = ["src/ui/**"]\nsummary = "x"\n\n[layers.app]\npaths = ["src/**"]\n'

    def test_first_matching_layer_in_file_order(self) -> None:
        layers = rules.parse_layers(self.text)
        self.assertEqual(list(layers), ["ui", "app"])
        self.assertEqual(rules.layer_of("src/ui/a.tsx", layers), "ui")
        self.assertEqual(rules.layer_of("src/core/a.ts", layers), "app")
        self.assertIsNone(rules.layer_of("README.md", layers))

    def test_refusals(self) -> None:
        for text in ("[layers.ui\n", '[layers.ui]\nsummary = "no paths"\n', "[layers.ui]\npaths = []\n", "layers = 3\n", "[layers]\nui = 1\n"):
            with self.subTest(text=text):
                with self.assertRaises(rules.RuleError):
                    rules.parse_layers(text)


class DueTest(unittest.TestCase):
    def test_only_matching_rules_this_context_has_not_had(self) -> None:
        python = rule("python", paths=("**/*.py",))
        everywhere = rule("everywhere")
        swift = rule("swift", paths=("**/*.swift",))
        self.assertEqual(rules.due((python, everywhere, swift), "a.py", ()), (python, everywhere))
        self.assertEqual(rules.due((python, everywhere, swift), "a.py", (str(python.path),)), (everywhere,))


class InjectionTest(unittest.TestCase):
    def test_whole_rules_with_where_they_are_and_the_layer_for_repository_rules(self) -> None:
        text = rules.injection((rule("testing", "Team body."), rule("api", "Repo body.", scope="acme-app")), "src/a.py", "acme-app", "core")
        self.assertIn("src/a.py in acme-app", text)
        self.assertIn("[asdlc] team rule `testing` (/board/plugins/team/rules/testing.md)\n\nTeam body.", text)
        self.assertIn("[asdlc] acme-app rule `api` (/board/plugins/acme-app/rules/api.md) - this file is in the `core` layer\n\nRepo body.", text)
        self.assertNotIn("layer", text.split("[asdlc] acme-app")[0])

    def test_plugin_root_becomes_the_plugins_folder(self) -> None:
        text = rules.injection((rule("api", "See {plugin_root}/skills/x/SKILL.md", scope="acme-app"),), "a", "acme-app", None)
        self.assertIn("See /board/plugins/acme-app/skills/x/SKILL.md", text)

    def test_a_long_rule_is_cut_at_the_cap_and_says_where_it_is(self) -> None:
        text = rules.injection((rule("huge", "x" * 50_000),), "a.py", "acme-app", None)
        self.assertLessEqual(len(text), rules.CAP)
        self.assertGreater(len(text), rules.CAP - 300)
        self.assertTrue(text.endswith("Read the rest at /board/plugins/team/rules/huge.md]"))

    def test_rules_that_dont_fit_still_say_where_they_are(self) -> None:
        many = tuple(rule(f"r{n}", "y" * 3_000) for n in range(6))
        text = rules.injection(many, "a.py", "acme-app", None)
        self.assertLessEqual(len(text), rules.CAP)
        for item in many:
            self.assertIn(str(item.path), text)
        self.assertIn("team rule `r5` also applies here: read it in full at /board/plugins/team/rules/r5.md", text)

    def test_cap_holds_for_any_mix(self) -> None:
        for count in range(1, 40):
            for size in (10, 900, 4_000, 12_000):
                text = rules.injection(tuple(rule(f"r{n}", "z" * size) for n in range(count)), "a.py", "acme-app", "ui")
                self.assertLessEqual(len(text), rules.CAP, (count, size))


class ForgetTest(unittest.TestCase):
    state = {"main": ["a"], "agent-1": ["b"]}

    def test_compact_and_clear_forget_only_the_main_context(self) -> None:
        for source in ("compact", "clear"):
            self.assertEqual(rules.forget(self.state, source), {"agent-1": ["b"]})

    def test_startup_forgets_everything_and_resume_nothing(self) -> None:
        self.assertEqual(rules.forget(self.state, "startup"), {})
        self.assertEqual(rules.forget(self.state, "resume"), self.state)

    def test_state_key(self) -> None:
        self.assertEqual((rules.state_key(None), rules.state_key(""), rules.state_key("ab12")), ("main", "main", "ab12"))


# --- the hook, against real repositories ---------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, **ISOLATED})
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class HookTest(unittest.TestCase):
    """A board with team and repository rules, a code repository pointing at it, and the hook."""

    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.root = Path(handle.name).resolve()
        self.board = self.root / "board"
        _write(self.board / "backlog" / "config.yml", "project_name: board\n")
        _write(self.board / "plugins" / "team" / "rules" / "testing.md", '---\npaths:\n  - "**/tests/**"\n---\n# Testing\n\nTeam testing rule.\n')
        _write(self.board / "plugins" / "team" / "rules" / "everywhere.md", "# Everywhere\n\nTeam rule for every file.\n")
        _write(self.board / "plugins" / "acme-app" / "rules" / "core.md", '---\npaths: ["src/core/**"]\n---\n# Core\n\nCore rule; see {plugin_root}/skills.\n')
        _write(self.board / "plugins" / "acme-app" / "layers.toml", '[layers.core]\npaths = ["src/core/**"]\n')
        _git(self.board, "init", "-q", "-b", "main")
        self.code = self.make_repo("app", "git@github.com:Acme/App.git")
        self.state = self.root / "state"
        self.project = self.root / "project"

    def make_repo(self, name: str, remote: str | None, board: Path | None = None) -> Path:
        repo = self.root / name
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        if remote:
            _git(repo, "remote", "add", "origin", remote)
        _git(repo, "config", "asdlc.board", str(board or self.board))
        _write(repo / "README.md", "x\n")
        _git(repo, "add", ".")
        _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "start")
        return repo

    def run_hook(self, payload: dict[str, object], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged = {**ISOLATED, "XDG_STATE_HOME": str(self.state), "CLAUDE_PROJECT_DIR": str(self.project), "ASDLC_BOARD": "", **(env or {})}
        return run_script("hooks/load_rules.py", stdin=json.dumps(payload), env=merged)

    def touch(self, path: Path, tool: str = "Read", session: str = "s1", agent: str | None = None, **env: str) -> dict[str, object]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        payload = {"session_id": session, "hook_event_name": "PostToolUse", "cwd": str(self.root), "tool_name": tool,
                   "tool_input": {"notebook_path" if tool == "NotebookEdit" else "file_path": str(path)}}
        if agent:
            payload["agent_id"] = agent
        done = self.run_hook(payload, env)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout) if done.stdout.strip() else {}

    def start(self, source: str, session: str = "s1") -> None:
        done = self.run_hook({"session_id": session, "hook_event_name": "SessionStart", "source": source, "cwd": str(self.root)})
        self.assertEqual((done.returncode, done.stdout), (0, ""), done.stderr)

    @staticmethod
    def context(output: dict[str, object]) -> str:
        return output.get("hookSpecificOutput", {}).get("additionalContext", "")

    def log(self) -> list[dict[str, str]]:
        path = self.project / ".asdlc" / "hooks.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_matching_rules_arrive_once_per_session(self) -> None:
        first = self.touch(self.code / "pkg" / "tests" / "test_a.py")
        text = self.context(first)
        self.assertEqual(first["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("Team testing rule.", text)
        self.assertIn("Team rule for every file.", text)
        self.assertNotIn("Core rule", text)
        self.assertIn("pkg/tests/test_a.py in acme-app", text)
        self.assertEqual(self.touch(self.code / "pkg" / "tests" / "test_b.py", tool="Edit"), {})
        entry = self.log()[-1]
        self.assertEqual((entry["hook"], entry["verdict"], entry["tool"]), ("load_rules", "allow", "Read"))
        self.assertIn("plugins/team/rules/testing.md", entry["reason"])

    def test_a_repository_rule_names_the_layer_and_its_plugin_folder(self) -> None:
        text = self.context(self.touch(self.code / "src" / "core" / "model.py", tool="Write"))
        self.assertIn("[asdlc] acme-app rule `core`", text)
        self.assertIn("this file is in the `core` layer", text)
        self.assertIn(f"see {self.board / 'plugins' / 'acme-app'}/skills.", text)
        self.assertIn("Team rule for every file.", text)
        self.assertNotIn("Team testing rule.", text)

    def test_each_subagent_is_its_own_context(self) -> None:
        self.assertIn("Team rule", self.context(self.touch(self.code / "a.py")))
        self.assertIn("Team rule", self.context(self.touch(self.code / "a.py", agent="worker-1")))
        self.assertEqual(self.touch(self.code / "a.py", agent="worker-1"), {})
        self.assertIn("Team rule", self.context(self.touch(self.code / "a.py", session="s2")))

    def test_compaction_brings_rules_back_for_the_main_context_only(self) -> None:
        self.touch(self.code / "a.py")
        self.touch(self.code / "a.py", agent="worker-1")
        self.start("compact")
        self.assertIn("Team rule", self.context(self.touch(self.code / "a.py")))
        self.assertEqual(self.touch(self.code / "a.py", agent="worker-1"), {})
        self.start("resume")
        self.assertEqual(self.touch(self.code / "a.py"), {})
        self.start("startup")
        self.assertIn("Team rule", self.context(self.touch(self.code / "a.py", agent="worker-1")))

    def test_a_task_worktree_finds_the_board_through_the_repository(self) -> None:
        worktree = self.root / "app.worktrees" / "task-1"
        _git(self.code, "worktree", "add", "-q", "-b", "task-1", str(worktree))
        text = self.context(self.touch(worktree / "src" / "core" / "x.py", tool="NotebookEdit"))
        self.assertIn("src/core/x.py in acme-app", text)
        self.assertIn("`core` layer", text)

    def test_no_board_no_repository_and_the_board_itself_get_nothing(self) -> None:
        plain = self.root / "plain"
        plain.mkdir()
        _git(plain, "init", "-q", "-b", "main")
        outside = self.root / "outside"
        outside.mkdir()
        self.assertEqual(self.touch(plain / "a.py"), {})
        self.assertEqual(self.touch(outside / "a.py"), {})
        self.assertEqual(self.touch(self.board / "plugins" / "team" / "rules" / "testing.md"), {})
        self.assertEqual(self.log(), [])

    def test_asdlc_board_points_any_repository_at_a_board(self) -> None:
        plain = self.root / "plain"
        plain.mkdir()
        _git(plain, "init", "-q", "-b", "main")
        self.assertIn("Team rule", self.context(self.touch(plain / "a.py", ASDLC_BOARD=str(self.board))))

    def test_a_repository_with_no_plugin_yet_or_no_origin_gets_the_team_rules(self) -> None:
        for name, remote in (("other", "https://github.com/acme/other.git"), ("local", None)):
            with self.subTest(repo=name):
                repo = self.make_repo(name, remote)
                text = self.context(self.touch(repo / "src" / "core" / "a.py", session=name))
                self.assertIn("Team rule for every file.", text)
                self.assertNotIn("Core rule", text)
                self.assertNotIn("layer", text)

    def test_a_rule_it_cannot_read_is_reported_once_and_the_rest_still_arrive(self) -> None:
        _write(self.board / "plugins" / "team" / "rules" / "broken.md", "---\npaths:\n---\nBody\n")
        first = self.touch(self.code / "a.py")
        self.assertIn("broken.md", first["systemMessage"])
        self.assertIn("lists no globs", first["systemMessage"])
        self.assertIn("Team rule for every file.", self.context(first))
        self.assertEqual(self.log()[-1]["verdict"], "error")
        self.assertEqual(self.touch(self.code / "b.py"), {})

    def test_a_broken_layers_file_is_reported_and_the_rule_arrives_without_a_layer(self) -> None:
        _write(self.board / "plugins" / "acme-app" / "layers.toml", "[layers.core\n")
        output = self.touch(self.code / "src" / "core" / "a.py")
        self.assertIn("layers.toml", output["systemMessage"])
        self.assertIn("Core rule", self.context(output))
        self.assertNotIn("layer", self.context(output).split("[asdlc] acme-app")[1].splitlines()[0])

    def test_the_cap_holds_end_to_end(self) -> None:
        _write(self.board / "plugins" / "acme-app" / "rules" / "huge.md", "# Huge\n\n" + "word " * 5_000)
        text = self.context(self.touch(self.code / "src" / "a.py"))
        self.assertLessEqual(len(text), rules.CAP)
        self.assertIn(str(self.board / "plugins" / "acme-app" / "rules" / "huge.md"), text)

    def test_an_unwritable_state_folder_delivers_every_time(self) -> None:
        blocked = self.root / "blocked"
        blocked.write_text("a file, not a folder")
        for _ in range(2):
            self.assertIn("Team rule", self.context(self.touch(self.code / "a.py", XDG_STATE_HOME=str(blocked))))

    def test_a_broken_payload_never_blocks_and_says_so(self) -> None:
        done = run_script("hooks/load_rules.py", stdin="not json", env={**ISOLATED, "CLAUDE_PROJECT_DIR": str(self.project)})
        self.assertEqual(done.returncode, 0)
        self.assertIn("load_rules failed", json.loads(done.stdout)["systemMessage"])
        self.assertEqual(self.log()[-1]["verdict"], "error")

    def test_a_tool_with_no_file_does_nothing(self) -> None:
        done = self.run_hook({"session_id": "s1", "hook_event_name": "PostToolUse", "cwd": str(self.root), "tool_name": "Read", "tool_input": {}})
        self.assertEqual((done.returncode, done.stdout), (0, ""))


class HookCommandTest(unittest.TestCase):
    """The rule loader's entries in hooks.json, which wrap uv like the guards'."""

    def entries(self) -> dict[str, dict[str, object]]:
        config = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
        found = {}
        for event in ("PostToolUse", "SessionStart"):
            for group in config[event]:
                for hook in group["hooks"]:
                    if "load_rules.py" in hook["command"]:
                        found[event] = {"matcher": group["matcher"], **hook}
        return found

    def test_runs_after_file_tools_and_on_the_starts_that_lose_context(self) -> None:
        entries = self.entries()
        self.assertEqual(entries["PostToolUse"]["matcher"], "Read|Edit|Write|NotebookEdit")
        self.assertEqual(entries["SessionStart"]["matcher"], "startup|clear|compact")

    def test_uv_failing_to_start_or_missing_never_blocks_and_says_so(self) -> None:
        command = self.entries()["PostToolUse"]["command"]
        bin_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bin_dir)
        fake = bin_dir / "uv"
        fake.write_text("#!/bin/sh\nexit 2\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        for path, says in ((f"{bin_dir}:/usr/bin:/bin", "could not start the rule loader"), ("/nonexistent", "uv is not installed, so the rule loader did not run")):
            with self.subTest(path=path):
                env = {**os.environ, "PATH": path, "CLAUDE_PLUGIN_ROOT": str(ROOT)}
                done = subprocess.run(["/bin/sh", "-c", command], input="{}", text=True, capture_output=True, env=env)
                self.assertEqual(done.returncode, 1)
                self.assertIn(says, done.stderr)


if __name__ == "__main__":
    unittest.main()
