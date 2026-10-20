"""Shared test helpers: throwaway git repositories and running scripts as subprocesses."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def make_repo() -> tuple[tempfile.TemporaryDirectory, Path]:
    """A throwaway repository on `main` with one commit. Keep the handle alive."""
    handle = tempfile.TemporaryDirectory()
    repo = Path(handle.name)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("test\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "start")
    return handle, repo


def commit_file(repo: Path, relative: str, text: str = "x\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", relative)
    git(repo, "commit", "-q", "-m", f"add {relative}")


def run_script(
    relative: str, *args: str, stdin: str = "", cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run one of this repository's scripts or hooks with the interpreter running the tests."""
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(ROOT / relative), *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=merged,
    )


def hook_payload(cwd: Path, tool: str, **tool_input: str) -> str:
    return json.dumps(
        {
            "session_id": "test",
            "hook_event_name": "PreToolUse",
            "cwd": str(cwd),
            "tool_name": tool,
            "tool_input": tool_input,
        }
    )


def load(relative: str):
    """Import one of this repository's scripts as a module, by path."""
    import importlib.util

    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module
