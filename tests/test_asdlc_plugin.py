import dataclasses
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
import unittest
from datetime import date
from pathlib import Path

from tests.support import ROOT, load, run_script

plugin = load("scripts/asdlc-plugin")

TODAY = date(2026, 10, 22)
# Every git call in these tests: no global or system config (no signing, no hooks path),
# and a fixed identity. ASDLC_CLAUDE empty: plugin validate is tested on its own below.
ISOLATED = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "ASDLC_CLAUDE": "",
}
CLAUDE = shutil.which("claude")


# --- the logic -------------------------------------------------------------------------

LAYERS = '[layers.domain]\npaths = ["src/shop/domain/**"]\nsummary = "Pure domain."\n\n[layers.services]\npaths = ["src/shop/services/**"]\ndepends_on = ["domain"]\n'
COMMANDS = '[build]\nrun = "true"\nverified = 2026-10-20\n\n[test]\nrun = "true"\nverified = 2026-10-20\n\n[lint]\nrun = "true"\nverified = 2026-10-20\n'
DOMAIN_RULE = '---\nlayer: domain\npaths:\n  - "src/shop/domain/**"\n---\n# The domain layer\n\nApplies to code in src/shop/domain.\n\n- No I/O.\n'
SERVICES_RULE = '---\nlayer: services\npaths: ["src/shop/services/**"]\n---\nApplies to src/shop/services.\n\n- See {plugin_root}/skills/add-order/SKILL.md and acme-shop:add-order.\n'
TESTING_RULE = '---\npaths:\n  - "tests/**/*.py"\n---\n# Testing\n\nApplies to the tests.\n'
SKILL = "---\nname: add-order\ndescription: How to add an order type end to end - the domain type, the service, the tests - load it before adding one, or the layers drift apart.\n---\n\n# Add an order\n"
TRACKED = ("src/shop/domain/order.py", "src/shop/services/checkout.py", "tests/test_order.py", "README.md")


def good() -> object:
    """A plugin with nothing wrong with it."""
    market = plugin.marketplace_with('{"name": "tasks", "plugins": [{"name": "team", "source": "./plugins/team"}]}',
                                     plugin.plugin_entry("acme-shop", "For acme/shop."))
    return plugin.PluginFiles(
        slug="acme-shop",
        manifest=json.dumps({"name": "acme-shop", "version": "0.1.0", "description": "For acme/shop.", "author": {"name": "The team"}}),
        marketplace=market,
        layers=LAYERS,
        commands=COMMANDS,
        rules=frozendict({"domain.md": DOMAIN_RULE, "services.md": SERVICES_RULE, "testing-python.md": TESTING_RULE}),
        skills=frozendict({"add-order": SKILL}),
        files=frozenset({".claude-plugin/plugin.json", "layers.toml", "commands.toml", "rules/domain.md", "rules/services.md",
                         "rules/testing-python.md", "skills/add-order/SKILL.md"}),
    )


def findings(files: object, tracked: tuple[str, ...] | None = TRACKED) -> list[str]:
    return [str(f) for f in plugin.check_plugin(files, TODAY, tracked, "<repo>")]


class SkeletonTest(unittest.TestCase):
    def test_names(self) -> None:
        self.assertEqual(plugin.display_name("git@github.com:Acme/Shop.git"), "Acme/Shop")
        self.assertEqual(plugin.display_name("https://gitlab.com/group/acme/shop"), "acme/shop")
        self.assertEqual(plugin.onboarding_path(Path("/src/tasks"), "acme-shop"), Path("/src/tasks.worktrees/plugin-acme-shop"))

    def test_the_skeleton_parses_and_is_unverified(self) -> None:
        files = plugin.skeleton("acme-shop", "acme/shop")
        self.assertEqual(sorted(files), [".claude-plugin/plugin.json", "commands.toml", "layers.toml"])
        self.assertEqual(json.loads(files[".claude-plugin/plugin.json"])["name"], "acme-shop")
        self.assertEqual(tomllib.loads(files["layers.toml"]), {})
        self.assertEqual(tomllib.loads(files["commands.toml"]), {"build": {"run": ""}, "test": {"run": ""}, "lint": {"run": ""}})

    def test_a_fresh_skeleton_says_what_is_left_to_do(self) -> None:
        files = plugin.skeleton("acme-shop", "acme/shop")
        bare = dataclasses.replace(good(), layers=files["layers.toml"], commands=files["commands.toml"], rules=frozendict(),
                                   skills=frozendict(), manifest=files[".claude-plugin/plugin.json"])
        found = "\n".join(findings(bare, None))
        for name in ("build", "test", "lint"):
            self.assertIn(f"[{name}] has no `run` command", found)
            self.assertIn(f"[{name}] is not verified: prove it with asdlc-plugin verify-command <repo> {name}", found)
        self.assertIn("has no testing rule", found)


class SkillTest(unittest.TestCase):
    """The onboard-repo skill and the script it drives must agree."""

    TEXT = (ROOT / "skills" / "onboard-repo" / "SKILL.md").read_text()

    def test_names_every_subcommand_it_needs_and_no_other(self) -> None:
        subcommands = set(plugin._parser()._subparsers._group_actions[0].choices)
        used = set(re.findall(r"asdlc-plugin ([a-z-]+) ", self.TEXT))
        self.assertEqual(used, subcommands)

    def test_frontmatter_and_house_style(self) -> None:
        fields = plugin.asdlc.frontmatter(self.TEXT)
        self.assertEqual(fields["name"], "onboard-repo")
        self.assertGreater(len(fields["description"]), 200)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/asdlc-plugin", self.TEXT)
        self.assertNotIn("—", self.TEXT)


class MarketplaceTest(unittest.TestCase):
    BASE = '{"name": "tasks", "owner": {"name": "T"}, "plugins": [{"name": "team", "source": "./plugins/team"}]}'

    def test_appends_and_keeps_everything_else(self) -> None:
        merged = json.loads(plugin.marketplace_with(self.BASE, plugin.plugin_entry("acme-shop", "d")))
        self.assertEqual(merged["owner"], {"name": "T"})
        self.assertEqual([p["name"] for p in merged["plugins"]], ["team", "acme-shop"])
        self.assertEqual(merged["plugins"][1]["source"], "./plugins/acme-shop")

    def test_replaces_its_own_entry_in_place(self) -> None:
        once = plugin.marketplace_with(self.BASE, plugin.plugin_entry("acme-shop", "old"))
        twice = plugin.marketplace_with(plugin.marketplace_with(once, plugin.plugin_entry("other", "o")), plugin.plugin_entry("acme-shop", "new"))
        self.assertEqual([(p["name"], p.get("description")) for p in json.loads(twice)["plugins"]],
                         [("team", None), ("acme-shop", "new"), ("other", "o")])

    def test_refuses_what_isnt_a_marketplace(self) -> None:
        for text in ("{", "[]", '{"plugins": {}}'):
            with self.subTest(text=text), self.assertRaises(plugin.PluginError):
                plugin.marketplace_with(text, plugin.plugin_entry("a-b", "d"))


class WithVerifiedTest(unittest.TestCase):
    def test_inserts_after_the_tables_last_line_and_changes_nothing_else(self) -> None:
        text = '# top\n[build]\nrun = "make"  # the build\n\n# about test\n[test]\nrun = "make test"\n'
        out = plugin.with_verified(text, "build", TODAY)
        self.assertEqual(out, '# top\n[build]\nrun = "make"  # the build\nverified = 2026-10-22\n\n# about test\n[test]\nrun = "make test"\n')

    def test_replaces_an_earlier_date(self) -> None:
        out = plugin.with_verified('[lint]\nverified = 2025-01-01\nrun = "x"\n', "lint", TODAY)
        self.assertEqual(out, '[lint]\nverified = 2026-10-22\nrun = "x"\n')

    def test_a_multi_line_run(self) -> None:
        text = '[test]\nrun = """\nmake test \\\n  && make e2e\n"""\ncwd = "app"\n\n[lint]\nrun = "x"\n'
        self.assertEqual(tomllib.loads(plugin.with_verified(text, "test", TODAY))["test"]["verified"], TODAY)

    def test_refuses_what_it_cant_edit_safely(self) -> None:
        for text, table in (('[build]\nrun = "x"\n', "test"), ('build = { run = "x" }\n', "build"), ("[build\n", "build")):
            with self.subTest(text=text), self.assertRaises(plugin.PluginError):
                plugin.with_verified(text, table, TODAY)


class CheckTest(unittest.TestCase):
    def test_a_good_plugin_has_no_findings(self) -> None:
        self.assertEqual(findings(good()), [])

    def test_every_finding_says_what_to_fix(self) -> None:
        g = good()
        rules = dict(g.rules)
        cases = {
            "`name` is 'acme'; it must be the slug": dataclasses.replace(g, manifest=g.manifest.replace('"acme-shop"', '"acme"')),
            "`version` must be MAJOR.MINOR.PATCH": dataclasses.replace(g, manifest=g.manifest.replace("0.1.0", "1")),
            "does not list 'acme-shop'": dataclasses.replace(g, marketplace='{"plugins": []}'),
            "it must be './plugins/acme-shop'": dataclasses.replace(g, marketplace=g.marketplace.replace("./plugins/acme-shop", "./x")),
            "layers.toml: is not valid TOML": dataclasses.replace(g, layers="[layers.x"),
            "[layers.domain] needs `paths`": dataclasses.replace(g, layers=LAYERS.replace('paths = ["src/shop/domain/**"]\n', "")),
            "[layers.services] depends on 'core'": dataclasses.replace(g, layers=LAYERS.replace('["domain"]', '["core"]')),
            "`/src/**` is absolute": dataclasses.replace(g, layers=LAYERS.replace('"src/shop/services/**"', '"/src/**"')),
            "[build] is missing": dataclasses.replace(g, commands=COMMANDS.replace("[build]", "[typecheck]")),
            "[lint] has no `run` command": dataclasses.replace(g, commands=COMMANDS.replace('[lint]\nrun = "true"', "[lint]")),
            "[test] is not verified": dataclasses.replace(g, commands=COMMANDS.replace('run = "true"\nverified = 2026-10-20\n\n[lint]', 'run = "true"\n\n[lint]')),
            "[e2e] is not verified": dataclasses.replace(g, commands=COMMANDS + '\n[e2e]\nrun = "x"\n'),
            "`verified` must be a bare TOML date": dataclasses.replace(g, commands=COMMANDS.replace("verified = 2026-10-20", 'verified = "yes"', 1)),
            "`verified` is 2026-12-01, after today": dataclasses.replace(g, commands=COMMANDS.replace("2026-10-20", "2026-12-01", 1)),
            "[build] has `verfied`": dataclasses.replace(g, commands=COMMANDS.replace("[build]\n", "[build]\nverfied = 1\n")),
            "has no `paths` frontmatter": dataclasses.replace(g, rules=frozendict(rules | {"testing-python.md": "# Testing\n\nApplies to tests.\n"})),
            "`paths` lists no globs": dataclasses.replace(g, rules=frozendict(rules | {"testing-python.md": "---\npaths: []\n---\nApplies to x.\n"})),
            'with one line saying when it applies: "Applies to ..."': dataclasses.replace(g, rules=frozendict(rules | {"domain.md": DOMAIN_RULE.replace("Applies to", "This is for")})),
            "keep a rule under 2,500": dataclasses.replace(g, rules=frozendict(rules | {"domain.md": DOMAIN_RULE + "x" * 2500})),
            "names layer 'core', which layers.toml doesn't define": dataclasses.replace(g, rules=frozendict(rules | {"domain.md": DOMAIN_RULE.replace("layer: domain", "layer: core")})),
            "its `paths` must be that layer's globs": dataclasses.replace(g, rules=frozendict(rules | {"domain.md": DOMAIN_RULE.replace('"src/shop/domain/**"', '"src/**"')})),
            "layer 'domain' has no rule": dataclasses.replace(g, rules=frozendict({k: v for k, v in rules.items() if k != "domain.md"})),
            "points at {plugin_root}/skills/add-order/SKILL.md, which is not in the plugin": dataclasses.replace(g, files=g.files - {"skills/add-order/SKILL.md"}),
            "names the skill acme-shop:add-order, but there is no skills/add-order": dataclasses.replace(g, skills=frozendict()),
            "has no testing rule": dataclasses.replace(g, rules=frozendict({k: v for k, v in rules.items() if k != "testing-python.md"})),
            "`name` is 'other'; leave it out or make it the folder's name": dataclasses.replace(g, skills=frozendict({"add-order": SKILL.replace("name: add-order", "name: other")})),
            "needs a `description`": dataclasses.replace(g, skills=frozendict({"add-order": "---\nname: add-order\n---\n"})),
            "skills/add-order/SKILL.md: missing": dataclasses.replace(g, skills=frozendict({"add-order": None})),
        }
        for says, files in cases.items():
            with self.subTest(finding=says):
                found = findings(files)
                self.assertTrue(any(says in f for f in found), found)

    def test_against_the_repositorys_files(self) -> None:
        g = good()
        moved = dataclasses.replace(g, layers=LAYERS.replace("src/shop/services/**", "src/shop/app/**"),
                                    rules=frozendict(g.rules | {"services.md": SERVICES_RULE.replace("src/shop/services/**", "src/shop/app/**")}))
        found = findings(moved)
        self.assertIn("plugins/acme-shop/layers.toml: [layers.services] matches no file in the repository: map only folders the code has", found)
        self.assertIn("plugins/acme-shop/rules/services.md: its `paths` match no file in the repository, so it would never be delivered", found)
        self.assertEqual(findings(moved, None), [], "without the repository's files, the layer map can't be checked against them")
        shadowed = dataclasses.replace(g, layers='[layers.code]\npaths = ["src/**"]\n\n' + LAYERS,
                                       rules=frozendict(g.rules | {"code.md": "---\nlayer: code\npaths: [\"src/**\"]\n---\nApplies to src.\n"}))
        found = findings(shadowed)
        self.assertTrue(any("[layers.domain] never applies: every file it matches is in an earlier layer (code)" in f for f in found), found)

    def test_validation_result(self) -> None:
        self.assertIs(plugin.validation_result(0, "√ Validation passed"), True)
        self.assertIs(plugin.validation_result(1, "× Validation failed"), False)
        self.assertIsNone(plugin.validation_result(127, "command not found"))
        self.assertEqual(plugin.validation_errors("× name bad\n\nPlugin directory checks for x\nLICENSE"), "× name bad")


# --- the script, against real git repositories ---------------------------------------------


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env={**os.environ, **ISOLATED})
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run_script("scripts/asdlc-plugin", *args, cwd=cwd, env={**ISOLATED, **(env or {})})


class World:
    """A tasks repository with a bare origin, and a small code repository pointed at it."""

    def __init__(self, test: unittest.TestCase) -> None:
        handle = tempfile.TemporaryDirectory()
        test.addCleanup(handle.cleanup)
        self.root = Path(handle.name).resolve()
        self.origin = self.root / "tasks-origin.git"
        _git(self.root, "init", "--quiet", "--bare", "-b", "main", str(self.origin))
        self.board = self.root / "tasks"
        _git(self.root, "init", "--quiet", "-b", "main", str(self.board))
        _write(self.board / "backlog" / "config.yml", "project_name: tasks\n")
        market = json.loads((ROOT / "templates" / "board" / ".claude-plugin" / "marketplace.json").read_text()) | {"name": "tasks"}
        _write(self.board / ".claude-plugin" / "marketplace.json", json.dumps(market, indent=2) + "\n")
        _git(self.board, "add", ".")
        _git(self.board, "commit", "--quiet", "-m", "board")
        _git(self.board, "remote", "add", "origin", str(self.origin))
        _git(self.board, "push", "--quiet", "origin", "main")
        _git(self.board, "fetch", "--quiet", "origin")

        self.code_origin = self.root / "acme" / "shop.git"
        _git(self.root, "init", "--quiet", "--bare", "-b", "main", str(self.code_origin))
        self.code = self.root / "shop"
        _git(self.root, "clone", "--quiet", str(self.code_origin), str(self.code))
        for path in TRACKED:
            _write(self.code / path, "x = 1\n")
        _write(self.code / "sub" / "marker", "")
        _git(self.code, "add", ".")
        _git(self.code, "commit", "--quiet", "-m", "start")
        _git(self.code, "push", "--quiet", "origin", "main")
        _git(self.code, "config", "asdlc.board", str(self.board))
        self.worktree = plugin.onboarding_path(self.board, "acme-shop")
        self.folder = self.worktree / "plugins" / "acme-shop"

    def scaffold(self) -> None:
        done = _run("scaffold", str(self.code))
        assert done.returncode == 0, done.stderr

    def fill(self) -> None:
        """What the onboarding skill writes, with commands that pass."""
        self.scaffold()
        _write(self.folder / "layers.toml", LAYERS)
        _write(self.folder / "commands.toml", COMMANDS.replace("verified = 2026-10-20\n", ""))
        for name, text in good().rules.items():
            _write(self.folder / "rules" / name, text)
        _write(self.folder / "skills" / "add-order" / "SKILL.md", SKILL)
        for name in ("build", "test", "lint"):
            done = _run("verify-command", str(self.code), name)
            assert done.returncode == 0, done.stdout + done.stderr

    def on_origin(self, path: str) -> str | None:
        done = subprocess.run(["git", "show", f"main:{path}"], cwd=self.origin, capture_output=True, text=True, env={**os.environ, **ISOLATED})
        return done.stdout if done.returncode == 0 else None


class StatusAndScaffoldTest(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World(self)

    def status(self) -> dict[str, object]:
        done = _run("status", str(self.world.code), "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_status_before_and_during_onboarding(self) -> None:
        self.assertEqual(self.status() | {"repo": "", "board": ""}, {"repo": "", "slug": "acme-shop", "board": "", "plugin": "plugins/acme-shop",
                                                                      "published": False, "onboarding": None, "fetched": True})
        text = _run("status", str(self.world.code))
        self.assertIn("acme-shop: no plugin yet", text.stdout)
        self.world.scaffold()
        self.assertEqual(self.status()["onboarding"], str(self.world.worktree))
        self.assertFalse(self.status()["published"])

    def test_status_refusals(self) -> None:
        _git(self.world.code, "remote", "remove", "origin")
        self.assertIn("has no `origin` remote", _run("status", str(self.world.code)).stderr)
        _git(self.world.code, "remote", "add", "origin", str(self.world.code_origin))
        _git(self.world.code, "config", "--unset", "asdlc.board")
        done = _run("status", str(self.world.code), env={"ASDLC_BOARD": ""})
        self.assertEqual(done.returncode, 1)
        self.assertIn("git config asdlc.board", done.stderr)

    def test_the_board_is_the_flag_then_the_environment_then_git_config(self) -> None:
        _git(self.world.code, "config", "asdlc.board", str(self.world.root / "not-a-board"))
        refused = _run("status", str(self.world.code), "--json")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("(from git config asdlc.board) is not a tasks repository", refused.stderr)
        found = _run("status", str(self.world.code), "--json", env={"ASDLC_BOARD": str(self.world.board)})
        self.assertEqual(json.loads(found.stdout)["board"], str(self.world.board), found.stderr)
        flagged = _run("--board", str(self.world.board), "status", str(self.world.code), "--json", env={"ASDLC_BOARD": str(self.world.code)})
        self.assertEqual(json.loads(flagged.stdout)["board"], str(self.world.board), flagged.stderr)

    def test_scaffold_opens_a_worktree_and_leaves_the_board_clone_alone(self) -> None:
        self.world.scaffold()
        for name in (".claude-plugin/plugin.json", "layers.toml", "commands.toml"):
            self.assertTrue((self.world.folder / name).is_file(), name)
        self.assertTrue((self.world.folder / "rules").is_dir())
        market = json.loads((self.world.worktree / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual([p["name"] for p in market["plugins"]], ["team", "acme-shop"])
        self.assertEqual(_git(self.world.board, "status", "--porcelain"), "", "the board clone must stay clean so asdlc keeps working")
        self.assertFalse((self.world.board / "plugins" / "acme-shop").exists())

    def test_scaffold_never_overwrites(self) -> None:
        self.world.scaffold()
        _write(self.world.folder / "commands.toml", "# ours\n")
        market = self.world.worktree / ".claude-plugin" / "marketplace.json"
        market.write_text(market.read_text().replace("Conventions, layers", "Our words"))
        before = market.read_text()
        done = _run("scaffold", str(self.world.code))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("created: nothing", done.stdout)
        self.assertEqual((self.world.folder / "commands.toml").read_text(), "# ours\n")
        self.assertEqual(market.read_text(), before)


class VerifyCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World(self)
        self.world.scaffold()
        self.commands = self.world.folder / "commands.toml"

    def verify(self, run: str, extra: str = "") -> subprocess.CompletedProcess[str]:
        _write(self.commands, f'# ours\n[build]\nrun = "true"\n\n[test]\nrun = {json.dumps(run)}\n{extra}\n[lint]\nrun = "true"\n')
        return _run("verify-command", str(self.world.code), "test")

    def test_success_writes_todays_date_into_that_table_only(self) -> None:
        done = self.verify("true")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        data = tomllib.loads(self.commands.read_text())
        self.assertEqual(data["test"]["verified"], date.today())
        self.assertNotIn("verified", data["build"])
        self.assertTrue(self.commands.read_text().startswith("# ours\n"))

    def test_failure_leaves_the_file_as_it_was_and_shows_the_tail(self) -> None:
        done = self.verify("echo first; echo the reason it failed; exit 3")
        before = self.commands.read_text()
        self.assertEqual(done.returncode, 1)
        self.assertIn("NOT verified", done.stdout)
        self.assertIn("exited 3", done.stdout)
        self.assertIn("the reason it failed", done.stdout)
        self.assertEqual(self.commands.read_text(), before)

    def test_a_command_that_changes_tracked_files_is_not_verified(self) -> None:
        done = self.verify("echo changed > README.md")
        self.assertEqual(done.returncode, 1)
        self.assertIn("a check must not change the code", done.stdout)
        self.assertNotIn("verified =", self.commands.read_text())

    def test_honours_cwd(self) -> None:
        self.assertEqual(self.verify("test -f marker", 'cwd = "sub"\n').returncode, 0)
        self.assertEqual(self.verify("test -f marker").returncode, 1)

    def test_a_clone_that_isnt_clean_at_the_default_branch_is_left_alone(self) -> None:
        _write(self.world.code / "README.md", "edited\n")
        done = self.verify("test \"$(cat README.md)\" = 'x = 1'")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        checkout = plugin.verify_checkout_path(self.world.code)
        self.assertIn(f"has uncommitted changes, so this runs in a clean checkout of origin/main at {checkout}", done.stderr)
        self.assertEqual((self.world.code / "README.md").read_text(), "edited\n", "the clone is never touched")

        other = self.world.root / "other-shop"
        _git(self.world.root, "clone", "--quiet", str(self.world.code_origin), str(other))
        _write(other / "NEW.md", "new\n")
        _git(other, "add", ".")
        _git(other, "commit", "--quiet", "-m", "newer")
        _git(other, "push", "--quiet", "origin", "main")
        _git(self.world.code, "checkout", "--quiet", "--", "README.md")
        done = self.verify("test -f NEW.md")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("not origin/main", done.stderr)

        self.assertEqual(self.verify("echo changed > README.md").returncode, 1)
        self.assertEqual(self.verify("test \"$(cat README.md)\" = 'x = 1'").returncode, 0, "the kept checkout is reset each time")

    def test_refuses_before_scaffold_and_without_a_command(self) -> None:
        self.assertIn("has no `run` command", self.verify("").stderr)
        shutil.rmtree(self.world.root / "tasks.worktrees")
        _git(self.world.board, "worktree", "prune")
        self.assertIn("run asdlc-plugin scaffold", _run("verify-command", str(self.world.code), "test").stderr)


class CheckScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World(self)

    def test_a_filled_plugin_is_clean_and_says_when_validate_did_not_run(self) -> None:
        self.world.fill()
        done = _run("--board", str(self.world.board), "check", "acme-shop", "--repo", str(self.world.code))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("acme-shop: clean", done.stdout)
        self.assertIn("claude plugin validate was not run: ASDLC_CLAUDE is set but empty", done.stderr)

    def test_the_board_is_found_through_repo(self) -> None:
        self.world.fill()
        done = _run("check", "acme-shop", "--repo", str(self.world.code), cwd=self.world.root, env={"ASDLC_BOARD": ""})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_findings_fail_the_check(self) -> None:
        self.world.scaffold()
        done = _run("check", "acme-shop", "--board", str(self.world.board), "--repo", str(self.world.code))
        self.assertEqual(done.returncode, 1)
        self.assertIn(f"[build] is not verified: prove it with asdlc-plugin verify-command {self.world.code} build", done.stdout)

    def test_refuses_another_repository_and_a_plugin_that_isnt_there(self) -> None:
        self.world.scaffold()
        self.assertIn("is acme-shop, not acme-other", _run("--board", str(self.world.board), "check", "acme-other", "--repo", str(self.world.code)).stderr)
        self.assertIn("there is no plugins/nobody-here", _run("--board", str(self.world.board), "check", "nobody-here").stderr)

    @unittest.skipIf(CLAUDE is None, "claude is not installed; the shape checks above stand in for plugin validate")
    def test_claude_plugin_validate_runs_on_the_plugin_and_the_marketplace(self) -> None:
        self.world.fill()
        done = _run("--board", str(self.world.board), "check", "acme-shop", env={"ASDLC_CLAUDE": CLAUDE})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("claude plugin validate passed on plugins/acme-shop", done.stderr)
        self.assertIn("claude plugin validate passed on the tasks repository", done.stderr)
        manifest = self.world.folder / ".claude-plugin" / "plugin.json"
        manifest.write_text(manifest.read_text().replace('"version": "0.1.0"', '"version": "0.1.0", "hooks": 5'))
        done = _run("--board", str(self.world.board), "check", "acme-shop", env={"ASDLC_CLAUDE": CLAUDE})
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("claude plugin validate failed", done.stdout)


class PublishTest(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World(self)

    def publish(self, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return _run("--board", str(self.world.board), "publish", "acme-shop", "--repo", str(self.world.code), env=env)

    def test_refuses_with_findings_and_pushes_nothing(self) -> None:
        self.world.scaffold()
        head = _git(self.world.origin, "rev-parse", "main")
        done = self.publish()
        self.assertEqual(done.returncode, 1)
        self.assertIn("not published", done.stderr)
        self.assertEqual(_git(self.world.origin, "rev-parse", "main"), head)
        self.assertTrue(self.world.worktree.is_dir(), "the work in progress stays")

    def test_publishes_with_hooks_off_and_brings_the_board_clone_up_to_date(self) -> None:
        self.world.fill()
        ran = self.world.root / "a-hook-ran"
        for hook in ("pre-commit", "pre-push", "reference-transaction"):
            _write(self.world.board / ".git" / "hooks" / hook, f"#!/bin/sh\necho {hook} >> '{ran}'\nexit 1\n")
            (self.world.board / ".git" / "hooks" / hook).chmod(0o755)
        done = self.publish()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse(ran.exists(), "a git hook ran")
        self.assertEqual(self.world.on_origin("plugins/acme-shop/layers.toml"), LAYERS)
        self.assertIn("verified = ", self.world.on_origin("plugins/acme-shop/commands.toml"))
        market = json.loads(self.world.on_origin(".claude-plugin/marketplace.json"))
        self.assertEqual([p["name"] for p in market["plugins"]], ["team", "acme-shop"])
        self.assertEqual(_git(self.world.origin, "log", "-1", "--format=%s", "main"), "Add the acme-shop plugin")
        self.assertEqual((self.world.board / "plugins" / "acme-shop" / "layers.toml").read_text(), LAYERS)
        self.assertFalse(self.world.worktree.exists())
        self.assertIn("--- record for the task's notes ---", done.stdout)
        self.assertIn("- build: `true`, verified ", done.stdout)
        self.assertIn("- domain: src/shop/domain/**", done.stdout)
        self.assertIn("Rules: domain.md, services.md, testing-python.md", done.stdout)
        self.assertIn("Skills: acme-shop:add-order", done.stdout)
        status = json.loads(_run("status", str(self.world.code), "--json").stdout)
        self.assertEqual((status["published"], status["onboarding"]), (True, None))

    def test_a_rejected_push_is_rebuilt_on_theirs_and_retried(self) -> None:
        self.world.fill()
        theirs = self.world.root / "theirs"
        _git(self.world.root, "clone", "--quiet", str(self.world.origin), str(theirs))
        market = theirs / ".claude-plugin" / "marketplace.json"
        market.write_text(plugin.marketplace_with(market.read_text(), plugin.plugin_entry("acme-web", "Another repository's plugin.")))
        _write(theirs / "plugins" / "acme-web" / "commands.toml", "# theirs\n")
        _git(theirs, "add", ".")
        _git(theirs, "commit", "--quiet", "-m", "Add the acme-web plugin")
        real_git = shutil.which("git")
        wrapper = self.world.root / "bin" / "git"
        flag = self.world.root / "interfered"
        _write(wrapper, "#!/bin/sh\n"
                        f'if [ "$1" = "push" ] && [ ! -e "{flag}" ]; then : > "{flag}"; "{real_git}" -C "{theirs}" push -q origin HEAD:main >&2; fi\n'
                        f'exec "{real_git}" "$@"\n')
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
        done = self.publish(env={"PATH": f"{wrapper.parent}{os.pathsep}{os.environ['PATH']}"})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(flag.exists(), "the other push never happened, so nothing was tested")
        self.assertIn("building on theirs and trying again", done.stderr)
        market = json.loads(self.world.on_origin(".claude-plugin/marketplace.json"))
        self.assertEqual([p["name"] for p in market["plugins"]], ["team", "acme-web", "acme-shop"])
        self.assertEqual(self.world.on_origin("plugins/acme-web/commands.toml"), "# theirs\n")
        self.assertEqual(self.world.on_origin("plugins/acme-shop/layers.toml"), LAYERS)

    def test_refuses_when_someone_else_published_the_same_plugin_meanwhile(self) -> None:
        self.world.fill()
        theirs = self.world.root / "theirs"
        _git(self.world.root, "clone", "--quiet", str(self.world.origin), str(theirs))
        _write(theirs / "plugins" / "acme-shop" / "commands.toml", "# theirs\n")
        _git(theirs, "add", ".")
        _git(theirs, "commit", "--quiet", "-m", "Their acme-shop plugin")
        _git(theirs, "push", "--quiet", "origin", "main")
        done = self.publish()
        self.assertEqual(done.returncode, 1)
        self.assertIn("changed on origin/main since this onboarding started", done.stderr)
        self.assertEqual(self.world.on_origin("plugins/acme-shop/commands.toml"), "# theirs\n")
        self.assertTrue(self.world.worktree.is_dir())

    def test_reopening_a_published_plugin_updates_it(self) -> None:
        self.world.fill()
        self.assertEqual(self.publish().returncode, 0)
        self.world.scaffold()
        rule = self.world.folder / "rules" / "domain.md"
        rule.write_text(rule.read_text() + "- Money is integer cents.\n")
        done = self.publish()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(_git(self.world.origin, "log", "-1", "--format=%s", "main"), "Update the acme-shop plugin")
        self.assertIn("integer cents", self.world.on_origin("plugins/acme-shop/rules/domain.md"))


if __name__ == "__main__":
    unittest.main()
