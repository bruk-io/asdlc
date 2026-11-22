"""What git knows: the repository, its branches, and what is on main."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

FETCH_LIMIT = 20.0
REMOTE_MAIN = "origin/main"


@dataclass(frozen=True)
class Ran:
    """How a program ended: whether it exited 0, and what it printed."""

    ok: bool
    out: str
    err: str


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


def file_at(root: Path, ref: str, path: str) -> str | None:
    """Give a file's text at a ref; None when the ref has no such file."""
    return _git(root, "show", f"{ref}:{path}")


def uncommitted(root: Path) -> tuple[str, ...]:
    """List the paths with a change that is not committed.

    Untracked files are among them, and files git ignores are not. An empty
    answer is a clean checkout.
    """
    entries = (_git(root, "status", "--porcelain", "-z") or "").split("\0")
    paths: list[str] = []
    renamed_from = False
    for entry in entries:
        if not renamed_from and len(entry) > 3:
            paths.append(entry[3:])
        # After a rename or a copy, the next entry is the path it came from.
        renamed_from = not renamed_from and bool(set(entry[:2]) & set("RC"))
    return tuple(paths)


def position(root: Path) -> str:
    """Give where the checkout is: its branch, or its commit when it is on none."""
    return current_branch(root) or (_git(root, "rev-parse", "HEAD") or "").strip()


def switch_back(root: Path, position: str) -> bool:
    """Put the checkout back where `position` found it; False when git refuses."""
    if has_branch(root, f"refs/heads/{position}"):
        return switch(root, position)
    return _git(root, "switch", "--quiet", "--detach", position) is not None


def checked_out(root: Path) -> dict[str, Path]:
    """Give each branch a worktree of the clone has checked out, and that worktree."""
    listed = _git(root, "worktree", "list", "--porcelain") or ""
    held = {}
    for block in listed.split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines())
        branch = fields.get("branch", "")
        if "worktree" in fields and branch.startswith("refs/heads/"):
            held[branch.removeprefix("refs/heads/")] = Path(fields["worktree"])
    return held


def held_elsewhere(root: Path) -> dict[str, str]:
    """Give each branch another worktree of the clone holds, and that worktree.

    `root` is the top of one worktree, which is the one left out.
    """
    here = root.resolve()
    return {
        branch: str(folder)
        for branch, folder in checked_out(root).items()
        if folder.resolve() != here
    }


def switch_new(root: Path, branch: str, ref: str) -> bool:
    """Make a branch at `ref` with no upstream and switch to it; False when refused.

    `create_branch` gives its branch the ref as an upstream. A task's branch is
    pushed under its own name, so it must not take `origin/main` as one.
    """
    made = _git(root, "switch", "--quiet", "--no-track", "--create", branch, ref)
    return made is not None


def delete_branch(root: Path, branch: str) -> bool:
    """Delete a local branch, merged or not; False when git refuses."""
    return _git(root, "branch", "--quiet", "-D", branch) is not None


def push_claim(root: Path, branch: str) -> Ran:
    """Push a branch to the remote, only if the remote has no branch of that name.

    The empty lease is what says "only if". `out` is what `git push --porcelain`
    printed, for `claimed` in `domain/build.py` to read: a push can exit 0 and
    have claimed nothing. Git is told not to ask for credentials.
    """
    lease = f"--force-with-lease={branch}:"
    done = subprocess.run(
        ["git", "-C", str(root), "push", "--porcelain", "-u", lease, "origin", branch],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return Ran(done.returncode == 0, done.stdout, done.stderr)


def head(root: Path) -> str:
    """Give the commit the checkout is on."""
    return (_git(root, "rev-parse", "HEAD") or "").strip()


def delete_remote(root: Path, branch: str, commit: str) -> bool:
    """Delete a branch from the remote, only while the remote has it at `commit`.

    The lease is what says "only while": a branch that has moved is someone
    else's by now, and is left. False when nothing was deleted.
    """
    lease = f"--force-with-lease={branch}:{commit}"
    done = subprocess.run(
        ["git", "-C", str(root), "push", "--quiet", lease, "origin", f":{branch}"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return done.returncode == 0


def commits(root: Path, span: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Give the commits of a range, oldest first, without merge commits.

    Each is `(id, subject, the files it changed)`. A commit always comes after
    the commits it was made on top of. Between two lines of history that a
    merge joined, the order is git's.
    """
    listed = _git(
        root,
        *("-c", "core.quotePath=false", "log", "--reverse", "--topo-order"),
        *("--no-merges", "--name-only", "--format=%x1e%H%x1f%s", span),
    )
    found = []
    for record in (listed or "").split("\x1e")[1:]:
        head, _, rest = record.partition("\n")
        id, _, subject = head.partition("\x1f")
        found.append((id, subject, tuple(line for line in rest.split("\n") if line)))
    return tuple(found)


def merge(root: Path, ref: str) -> bool:
    """Merge a ref into the checkout's branch; False when it did not merge cleanly.

    A merge that conflicts is left as git left it.
    """
    return _git(root, "merge", "--quiet", "--no-edit", ref) is not None


def conflicts(root: Path) -> tuple[str, ...]:
    """List the files a merge left in conflict."""
    listed = _git(root, "diff", "--name-only", "--diff-filter=U") or ""
    return tuple(line for line in listed.split("\n") if line)


def merging(root: Path) -> bool:
    """Say whether a merge is in progress in the checkout."""
    return _git(root, "rev-parse", "--verify", "--quiet", "MERGE_HEAD") is not None
