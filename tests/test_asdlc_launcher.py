import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, load

launcher = load("scripts/asdlc_launcher.py")

CACHE = Path("/home/kyle/.claude/plugins/cache/asdlc/asdlc")


def record(version: str, *, project: str | None = None, scope: str = "local", updated: str = "2026-11-01T00:00:00.000Z") -> dict[str, str]:
    row = {"scope": scope, "installPath": str(CACHE / version), "version": version, "lastUpdated": updated, "gitCommitSha": "2ac9e69c03096bbf48da48c8b29ebfff8d3ccddb"}
    return row | ({"projectPath": project} if project else {})


def records(*rows: dict[str, str], plugin: str = "asdlc@asdlc") -> str:
    return json.dumps({"version": 2, "plugins": {plugin: list(rows), "other@market": [record("9.9.9", scope="user")]}})


class InstallRecordsTest(unittest.TestCase):
    def test_only_the_asdlc_plugins_installs_are_read(self) -> None:
        found = launcher.installs(records(record("0.2.0", project="/home/kyle/steg"), record("0.2.0", scope="user")))
        self.assertEqual([(i.root, i.version, i.project) for i in found],
                         [(CACHE / "0.2.0", "0.2.0", Path("/home/kyle/steg")), (CACHE / "0.2.0", "0.2.0", None)])
        self.assertEqual(found[0].commit, "2ac9e69c03096bbf48da48c8b29ebfff8d3ccddb")

    def test_a_plugin_of_the_same_name_from_any_marketplace_counts(self) -> None:
        self.assertEqual(len(launcher.installs(records(record("0.2.0", scope="user"), plugin="asdlc@tasks"))), 1)

    def test_a_file_that_is_not_the_records_is_no_installs(self) -> None:
        for text in ("", "not json", "[]", '{"plugins": []}', '{"plugins": {"asdlc@asdlc": "x"}}', '{"plugins": {"asdlc@asdlc": [{"scope": "user"}]}}'):
            with self.subTest(text=text):
                self.assertEqual(launcher.installs(text), ())


class PluginBinTest(unittest.TestCase):
    def test_the_folders_whose_bin_is_on_the_path(self) -> None:
        entries = ["/usr/bin", "/home/kyle/.local/bin", str(CACHE / "0.2.0" / "bin"), "", "relative/bin", str(CACHE / "0.2.0" / "bin")]
        self.assertEqual(launcher.bin_parents(entries), (Path("/usr"), Path("/home/kyle/.local"), CACHE / "0.2.0"))


class ChooseTest(unittest.TestCase):
    def choose(self, *rows: dict[str, str], session: tuple[Path, ...] = (), cwd: str = "/home/kyle/steg") -> object:
        return launcher.choose(session, launcher.installs(records(*rows)), Path(cwd))

    def test_a_session_that_loaded_the_plugin_decides(self) -> None:
        """Inside Claude Code the plugin's bin folder is on PATH: that is the release the session loaded, whatever was installed since."""
        loaded = Path("/home/kyle/asdlc.worktrees/try/")
        chosen = self.choose(record("0.3.0", scope="user"), session=(loaded, CACHE / "0.2.0"))
        self.assertEqual((chosen.root, chosen.source), (loaded, "the plugin this session loaded"))

    def test_the_install_for_the_folder_you_are_in_comes_next(self) -> None:
        rows = (record("0.3.0", scope="user", updated="2026-11-09T00:00:00.000Z"), record("0.2.0", project="/home/kyle/steg"),
                record("0.1.0", project="/home/kyle"))
        for cwd in ("/home/kyle/steg", "/home/kyle/steg/crates/core"):
            with self.subTest(cwd=cwd):
                chosen = self.choose(*rows, cwd=cwd)
                self.assertEqual((chosen.root, chosen.source), (CACHE / "0.2.0", "the install for /home/kyle/steg"))

    def test_a_folder_that_only_starts_with_the_same_letters_is_not_inside(self) -> None:
        chosen = self.choose(record("0.2.0", project="/home/kyle/steg"), record("0.3.0", scope="user"), cwd="/home/kyle/steg-two")
        self.assertEqual(chosen.root, CACHE / "0.3.0")

    def test_then_the_install_for_every_project(self) -> None:
        chosen = self.choose(record("0.2.0", project="/home/kyle/other", updated="2026-11-09T00:00:00.000Z"), record("0.3.0", scope="user"))
        self.assertEqual((chosen.root, chosen.source), (CACHE / "0.3.0", "the install for every project"))

    def test_then_the_newest_install_of_any_project(self) -> None:
        chosen = self.choose(record("0.2.0", project="/home/kyle/a", updated="2026-11-02T00:00:00.000Z"),
                             record("0.3.0", project="/home/kyle/b", updated="2026-11-09T00:00:00.000Z"), cwd="/tmp")
        self.assertEqual((chosen.root, chosen.source), (CACHE / "0.3.0", "the newest install, made for /home/kyle/b"))

    def test_nothing_installed_is_no_release(self) -> None:
        self.assertIsNone(launcher.choose((), (), Path("/home/kyle/steg")))


def fake_plugin(root: Path, says: str) -> Path:
    """A folder shaped like the installed plugin, whose two scripts print what they were given."""
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "asdlc", "version": "0.2.0"}))
    (root / "scripts").mkdir()
    (root / "bin").mkdir()
    for name in launcher.COMMANDS:
        (root / "scripts" / name).write_text(f"import sys\nprint({says!r}, {name!r}, *sys.argv[1:])\n")
    return root


@unittest.skipUnless(shutil.which("uv"), "uv is not installed")
class LauncherRunTest(unittest.TestCase):
    """The launcher as a person has it: a copy named asdlc in a folder on PATH, far from any clone."""

    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.home = Path(handle.name).resolve()
        self.plugins = self.home / "plugins"
        self.installed = fake_plugin(self.plugins / "cache" / "asdlc" / "asdlc" / "0.2.0", "installed")
        (self.home / "bin").mkdir()
        for name in launcher.COMMANDS:
            shutil.copy(ROOT / "scripts" / "asdlc_launcher.py", self.home / "bin" / name)

    def write_records(self, *rows: dict[str, str]) -> None:
        (self.plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {"asdlc@asdlc": list(rows)}}))

    def run_launcher(self, name: str, *args: str, path: str = "") -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "CLAUDE_CODE_PLUGIN_CACHE_DIR": str(self.plugins), "PATH": f"{path}{os.pathsep if path else ''}{os.environ['PATH']}"}
        return subprocess.run([sys.executable, str(self.home / "bin" / name), *args], capture_output=True, text=True, cwd=self.home, env=env)

    def test_each_command_reaches_the_installed_plugins_script(self) -> None:
        self.write_records({"scope": "user", "installPath": str(self.installed), "version": "0.2.0"})
        for name in launcher.COMMANDS:
            with self.subTest(name=name):
                done = self.run_launcher(name, "next", "--as", "kyle.w1")
                self.assertEqual((done.returncode, done.stdout.strip()), (0, f"installed {name} next --as kyle.w1"), done.stderr)

    def test_a_session_runs_the_plugin_it_loaded_not_the_newer_install(self) -> None:
        self.write_records({"scope": "user", "installPath": str(self.installed), "version": "0.2.0"})
        loaded = fake_plugin(self.home / "loaded", "loaded")
        done = self.run_launcher("asdlc", "whoami", path=f"{self.home / 'bin'}{os.pathsep}{loaded / 'bin'}")
        self.assertEqual(done.stdout.strip(), "loaded asdlc whoami", done.stderr)

    def test_a_bin_folder_of_another_plugin_is_not_followed(self) -> None:
        self.write_records({"scope": "user", "installPath": str(self.installed), "version": "0.2.0"})
        other = fake_plugin(self.home / "other", "other")
        (other / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "team"}))
        self.assertEqual(self.run_launcher("asdlc", "whoami", path=str(other / "bin")).stdout.strip(), "installed asdlc whoami")

    def test_an_install_whose_folder_is_gone_is_passed_over(self) -> None:
        self.write_records({"scope": "local", "projectPath": str(self.home), "installPath": str(self.home / "gone"), "version": "0.1.0"},
                           {"scope": "user", "installPath": str(self.installed), "version": "0.2.0"})
        self.assertEqual(self.run_launcher("asdlc", "whoami").stdout.strip(), "installed asdlc whoami")

    def test_no_installed_plugin_says_so_and_how_to_get_one(self) -> None:
        done = self.run_launcher("asdlc", "whoami")
        self.assertEqual((done.returncode, done.stdout), (1, ""))
        for says in ("no installed asdlc plugin", str(self.plugins / "installed_plugins.json"), "/plugin install asdlc", "scripts/asdlc"):
            with self.subTest(says=says):
                self.assertIn(says, done.stderr)

    def test_a_copy_under_another_name_refuses(self) -> None:
        shutil.copy(ROOT / "scripts" / "asdlc_launcher.py", self.home / "bin" / "something")
        done = self.run_launcher("something")
        self.assertEqual(done.returncode, 1)
        self.assertIn("asdlc or asdlc-plugin", done.stderr)


if __name__ == "__main__":
    unittest.main()
