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


def task_text(step: int, requirement: str, size: int, title: str) -> str:
    """Give a task document as `asdlc task new` writes its frontmatter."""
    front = f"kind: task\nstep: {step}\ndelivers: [{requirement}]\nsize: {size}\n"
    return f"---\n{front}---\n# Task: {title}\n"


# What the remote's main holds: one intent with its spec, its plan and two tasks
# that depend on nothing, one of size 2 and one of size 8, and the checks.
ACCEPTED = {
    "intent/claims/intent.md": "---\nkind: intent\nauthor: a\n---\n# Intent: claims\n",
    "intent/claims/spec.md": (
        "---\nkind: spec\n---\n# Spec: claims\n### R1: one\n### R2: two\n"
    ),
    "intent/claims/plan.md": (
        "---\nkind: plan\n---\n# Plan: claims\n"
        "## Files that change\n- api/status.py (new)\n## Order of work\n"
        "### Step 1: the endpoint\n- delivers: R1\n"
        "### Step 2: the panel\n- delivers: R2\n"
    ),
    "intent/claims/tasks/01-endpoint/task.md": task_text(1, "R1", 2, "the endpoint"),
    "intent/claims/tasks/02-panel/task.md": task_text(2, "R2", 8, "the panel"),
    ".asdlc/checks": "echo checked\n",
}


def commit_files(root: Path, texts: dict[str, str], subject: str) -> None:
    """Write files into a working tree and commit them."""
    for relative, text in texts.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", subject)


def clone_of(origin: Path, folder: Path) -> Path:
    """Clone a bare repository into a new folder, with a name and an email set."""
    git(origin.parent, "clone", "-q", str(origin), str(folder))
    git(folder, "config", "user.name", "Dana")
    git(folder, "config", "user.email", "dana@example.com")
    return folder


def second_clone(remote: Path) -> Path:
    """Give another clone of the `remote` fixture's origin, beside the first."""
    return clone_of(remote.parent / "origin.git", remote.parent / "second")


@pytest.fixture
def remote(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A clone whose `origin` is a bare repository beside it, on disk.

    The remote's main holds `ACCEPTED`, in one commit, and the clone is on main at
    that commit. Nothing here reaches the network.
    """
    base = tmp_path_factory.mktemp("remote").resolve()
    origin = base / "origin.git"
    git(base, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = base / "seed"
    git(base, "init", "-q", "-b", "main", str(seed))
    commit_files(seed, ACCEPTED, "claims, accepted")
    git(seed, "push", "-q", str(origin), "main")
    return clone_of(origin, base / "clone")
