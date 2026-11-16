import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def git(root: Path, *args: str) -> str:
    command = [
        "git",
        "-C",
        str(root),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        *args,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def example() -> Path:
    """The worked example: four intents, two replacing a requirement of the first."""
    return ROOT / "examples" / "claims"


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A git repository whose main holds one accepted intent."""
    root = tmp_path.resolve()
    git(root, "init", "-q", "-b", "main")
    intent = root / "intent" / "claims" / "intent.md"
    intent.parent.mkdir(parents=True)
    intent.write_text("---\nkind: intent\nauthor: a\n---\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "intent")
    return root
