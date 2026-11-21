"""What git knows: the repository, its branches, and what is on main."""

import os
import subprocess
from pathlib import Path

FETCH_LIMIT = 20.0


def _git(root: Path, *args: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )
    return done.stdout if done.returncode == 0 else None


def has_remote(root: Path) -> bool:
    """Say whether the repository has a remote named `origin`."""
    return _git(root, "remote", "get-url", "origin") is not None


def fetch(root: Path, limit: float = FETCH_LIMIT) -> bool:
    """Bring what is known of the remote up to date; False when that did not work.

    It never asks for credentials: git is told not to prompt, and it runs with no
    terminal to ask on. It gives up after `limit` seconds. Nothing is read back,
    so no pipe is left to wait on when git is stopped at the limit.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "fetch", "--prune", "origin"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            start_new_session=True,
            timeout=limit,
        )
    except subprocess.TimeoutExpired:
        return False
    return done.returncode == 0


def document_texts_at(
    root: Path, ref: str, prefix: str = ""
) -> tuple[tuple[str, str], ...]:
    """Read every Markdown file under `<prefix>intent/` at a ref.

    Each is `(path from the prefix, text)`, the shape `files.document_texts`
    gives. `prefix` is empty for the repository's root, and otherwise a folder
    below it that ends in a slash.
    """
    folder = f"{prefix}intent"
    listed = _git(root, "ls-tree", "-r", "-z", "--name-only", ref, "--", folder)
    paths = sorted(path for path in (listed or "").split("\0") if path.endswith(".md"))
    texts = ((path, _git(root, "show", f"{ref}:{path}")) for path in paths)
    return tuple(
        (path.removeprefix(prefix), text) for path, text in texts if text is not None
    )


def remote_branches(root: Path) -> frozenset[str]:
    """List the branches the remote had when it was last fetched, without `origin/`."""
    listed = _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes/origin")
    names = (
        line.strip().removeprefix("refs/remotes/origin/")
        for line in (listed or "").split("\n")
    )
    return frozenset(name for name in names if name and name != "HEAD")


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


def ahead(root: Path, ref: str) -> int:
    """Count the commits the current branch has that `ref` does not."""
    counted = _git(root, "rev-list", "--count", f"{ref}..HEAD")
    return int(counted) if counted else 0


def commit_empty(root: Path, subject: str) -> bool:
    """Add a commit that changes no file, whatever is staged; False when git refuses.

    The commit carries its parent's tree, so the index and the working tree are
    left as they were. Git refuses when it cannot tell who is committing.
    """
    made = _git(root, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", subject)
    if made is None:
        return False
    return _git(root, "reset", "--quiet", "--soft", made.strip()) is not None


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


def setting(root: Path, key: str) -> str:
    """Give what git's configuration holds for a key; empty when it is not set."""
    return (_git(root, "config", "--get", key) or "").strip()


def has_branch(root: Path, branch: str) -> bool:
    return _git(root, "rev-parse", "--verify", "--quiet", branch) is not None


def changed_since(root: Path, ref: str, branch: str = "HEAD") -> tuple[str, ...]:
    """List the files a branch changed since it left `ref`."""
    listed = _git(root, "diff", "--name-only", f"{ref}...{branch}") or ""
    return tuple(line for line in listed.split("\n") if line)
