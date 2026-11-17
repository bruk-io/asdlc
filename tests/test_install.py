"""The session-start install: real uv on this checkout, and its one decision.

`plugins/asdlc/scripts/install` is shell, because it runs before the package is
there. The first test runs it as a session would. The rest stand a recording `uv`
in for the real one, to show when the script asks for an install.
"""

import json
import os
import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path

import pytest

from tests.conftest import ROOT

PLUGIN = ROOT / "plugins" / "asdlc"
SYSTEM = "/usr/bin:/bin"


def program(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


def install(plugin: Path, home: Path, path: str, session: str = "s1"):
    """Run the script as a session start would, with every folder under `home`."""
    (home / "tmp").mkdir(exist_ok=True)
    env = os.environ | {
        "CLAUDE_PLUGIN_ROOT": str(plugin),
        "CLAUDE_PLUGIN_DATA": str(home / "data"),
        "CLAUDE_ENV_FILE": str(home / "env"),
        "TMPDIR": str(home / "tmp"),
        "PATH": path,
        "UV_LOG": str(home / "uv.log"),
    }
    return subprocess.run(
        [str(plugin / "scripts" / "install")],
        input=json.dumps({"session_id": session, "source": "startup"}),
        env=env,
        capture_output=True,
        text=True,
    )


def test_a_session_runs_the_package_it_shipped_ahead_of_an_older_asdlc(tmp_path):
    done = install(PLUGIN, tmp_path, os.environ["PATH"])
    assert (done.returncode, done.stdout) == (0, ""), done.stderr

    older = program(tmp_path / "older" / "asdlc", "#!/bin/sh\necho old\n")
    path = f"{older.parent}:{os.environ['PATH']}"
    ran = subprocess.run(
        ["sh", "-c", f'. "{tmp_path / "env"}"; command -v asdlc; asdlc version'],
        env=os.environ | {"PATH": path},
        capture_output=True,
        text=True,
    )
    found, printed = ran.stdout.strip().split("\n")
    assert found == str(tmp_path / "tmp" / "asdlc-s1" / "bin" / "asdlc")
    assert printed == version("asdlc")

    # The hooks call the copy that outlasts the session, and python is not shadowed.
    assert (tmp_path / "data" / "asdlc" / "venv" / "bin" / "asdlc").is_file()
    assert os.listdir(tmp_path / "tmp" / "asdlc-s1" / "bin") == ["asdlc"]


def test_installing_from_a_checkout_writes_nothing_into_it(tmp_path):
    """Sessions that start together must not build in the tree they share.

    Each has a lock of its own, so a build that wrote into the checkout would be
    written over by the next one. Some of those sessions then got no command.
    """
    checkout = tmp_path / "checkout"
    shutil.copytree(PLUGIN, checkout / "plugins" / "asdlc")
    shutil.copytree(
        ROOT / "src" / "asdlc",
        checkout / "src" / "asdlc",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for name in ("pyproject.toml", "README.md"):
        shutil.copy(ROOT / name, checkout / name)
    before = sorted(path.relative_to(checkout) for path in checkout.rglob("*"))

    done = install(checkout / "plugins" / "asdlc", tmp_path, os.environ["PATH"])

    assert (done.returncode, done.stdout) == (0, ""), done.stderr
    assert sorted(path.relative_to(checkout) for path in checkout.rglob("*")) == before
    assert (tmp_path / "tmp" / "asdlc-s1" / "bin" / "asdlc").exists()


STAND_IN = """#!/bin/sh
# Records how uv was called, and leaves what the real one would: a python for
# `venv`, an asdlc beside it for `pip install`.
echo "$*" >>"$UV_LOG"
for last; do :; done
if [ "$1" = venv ]; then
    mkdir -p "$last/bin"
    printf '#!/bin/sh\\n' >"$last/bin/python"
    chmod +x "$last/bin/python"
fi
if [ "$1" = pip ]; then
    while [ "$#" -gt 0 ]; do
        [ "$1" = --python ] && bin="$(dirname "$2")"
        shift
    done
    printf '#!/bin/sh\\necho stand-in\\n' >"$bin/asdlc"
    chmod +x "$bin/asdlc"
fi
"""


@pytest.fixture
def installed(tmp_path: Path) -> tuple[Path, Path, str]:
    """A copy of the plugin's folder alone, as an installed plugin is, and a uv."""
    plugin = tmp_path / "cache" / "asdlc"
    shutil.copytree(PLUGIN, plugin)
    program(tmp_path / "stand-in" / "uv", STAND_IN)
    return plugin, tmp_path, f"{tmp_path / 'stand-in'}:{SYSTEM}"


def installs(home: Path) -> list[str]:
    log = home / "uv.log"
    lines = log.read_text().splitlines() if log.exists() else []
    return [line for line in lines if line.startswith("pip install")]


def test_an_installed_plugin_fetches_the_repository_once_for_a_version(installed):
    plugin, home, path = installed
    wanted = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())

    first = install(plugin, home, path)
    assert (first.returncode, first.stdout) == (0, ""), first.stderr
    assert len(installs(home)) == 1
    assert installs(home)[0].endswith("git+https://github.com/bruk-io/asdlc@main")
    stamp = home / "data" / "asdlc" / "installed"
    assert stamp.read_text().strip() == wanted["version"]

    again = install(plugin, home, path, session="s2")
    assert again.returncode == 0, again.stderr
    assert len(installs(home)) == 1
    assert (home / "tmp" / "asdlc-s2" / "bin" / "asdlc").exists()


def test_an_installed_plugin_installs_again_when_its_version_moves(installed):
    plugin, home, path = installed
    install(plugin, home, path)
    (home / "data" / "asdlc" / "installed").write_text("0.0.1\n")

    assert install(plugin, home, path).returncode == 0
    assert len(installs(home)) == 2


def test_a_lock_whose_owner_has_gone_is_taken_over(installed):
    plugin, home, path = installed
    gone = subprocess.Popen(["true"])
    gone.wait()
    lock = home / "data" / "asdlc" / "lock"
    lock.mkdir(parents=True)
    (lock / "pid").write_text(f"{gone.pid}\n")

    assert install(plugin, home, path).returncode == 0
    assert not lock.exists()


def test_without_uv_it_says_why_and_puts_nothing_on_stdout(installed):
    plugin, home, _ = installed
    bare = home / "bare"
    bare.mkdir()
    (bare / "cat").symlink_to(shutil.which("cat"))
    done = install(plugin, home, str(bare))
    assert (done.returncode, done.stdout) == (1, "")
    assert "uv is not installed" in done.stderr
    assert "its lint and its guard will not run" in done.stderr
