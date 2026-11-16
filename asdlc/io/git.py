"""What git knows: the repository, its branches, and what is on main."""

import subprocess
from pathlib import Path


def _git(root: Path, *args: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )
    return done.stdout if done.returncode == 0 else None


def repository(folder: Path) -> Path | None:
    """Give the root of the git repository a folder is in; None when it is in none."""
    top = _git(folder, "rev-parse", "--show-toplevel")
    return Path(top.strip()) if top else None


def base(root: Path) -> str | None:
    """Give the ref that stands for main: the remote's when there is one.

    Return None when the repository has no main at all.
    """
    for ref in ("origin/main", "main"):
        if _git(root, "rev-parse", "--verify", "--quiet", ref) is not None:
            return ref
    return None


def current_branch(root: Path) -> str:
    return (_git(root, "branch", "--show-current") or "").strip()


def documents_on(root: Path, ref: str) -> frozenset[str]:
    """List the files under `intent/` at a ref."""
    listed = _git(root, "ls-tree", "-r", "--name-only", ref, "--", "intent") or ""
    return frozenset(listed.split())


def create_branch(root: Path, name: str, ref: str) -> bool:
    """Make a branch at `ref` and switch to it; False when git refuses."""
    return _git(root, "switch", "--quiet", "--create", name, ref) is not None


def switch(root: Path, name: str) -> bool:
    """Switch to a branch that exists; False when git refuses."""
    return _git(root, "switch", "--quiet", name) is not None


def hooks_folder(root: Path) -> Path:
    """Give the folder git runs this repository's hooks from."""
    listed = _git(root, "rev-parse", "--git-path", "hooks") or ".git/hooks"
    folder = Path(listed.strip())
    return folder if folder.is_absolute() else root / folder


def branches(root: Path) -> frozenset[str]:
    """List the branches that exist here or on the remote, without a remote prefix."""
    listed = _git(
        root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes"
    )
    names = (line.strip() for line in (listed or "").split("\n"))
    return frozenset(name.removeprefix("origin/") for name in names if name)


def merge_subjects(root: Path, ref: str) -> tuple[str, ...]:
    """Give the subject of every merge commit on a ref's first-parent line."""
    listed = _git(root, "log", "--first-parent", "--merges", "--format=%s", ref) or ""
    return tuple(line for line in listed.split("\n") if line)


def user_name(root: Path) -> str:
    return (_git(root, "config", "user.name") or "").strip()


def has_branch(root: Path, branch: str) -> bool:
    return _git(root, "rev-parse", "--verify", "--quiet", branch) is not None


def changed_since(root: Path, ref: str, branch: str = "HEAD") -> tuple[str, ...]:
    """List the files a branch changed since it left `ref`."""
    listed = _git(root, "diff", "--name-only", f"{ref}...{branch}") or ""
    return tuple(line for line in listed.split("\n") if line)
