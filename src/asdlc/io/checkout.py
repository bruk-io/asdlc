"""What a command reads before it decides: the remote, GitHub and the checkout.

Each fact is one call to git or to `gh`, gathered into one record so that the
decision in `domain/build.py` is made from plain data. Nothing is decided here.
"""

from pathlib import Path

from asdlc.domain import scaffold
from asdlc.domain.build import CHECKS, Found
from asdlc.domain.documents import Kind
from asdlc.domain.tasks import branch_of
from asdlc.io import files, git, github
from asdlc.io.git import REMOTE_MAIN


def _held_elsewhere(root: Path) -> dict[str, str]:
    """Give each branch another worktree of the clone holds, and that worktree."""
    here = root.resolve()
    return {
        branch: str(folder)
        for branch, folder in git.checked_out(root).items()
        if folder.resolve() != here
    }


def found(root: Path, id: str) -> Found:
    """Read what a start of the task `<slug>/<task>` decides from.

    `root` is the top of the checkout. The remote is read as it was last
    fetched, so the caller fetches first.
    """
    slug, name = id.split("/")
    branch = f"refs/heads/{branch_of(id)}"
    document = scaffold.path(Kind.TASK, slug, name)
    here = files.read_text(root / document) is not None
    return Found(
        remote=git.has_remote(root),
        main=git.has_branch(root, REMOTE_MAIN),
        pulls=github.open_pulls(root),
        checks=git.file_at(root, REMOTE_MAIN, CHECKS),
        uncommitted=git.uncommitted(root),
        texts=git.document_texts_at(root, REMOTE_MAIN),
        branches=git.remote_branches(root),
        merges=git.merge_subjects(root, REMOTE_MAIN),
        cut=here or git.file_at(root, f"origin/tasks/{slug}", document) is not None,
        on=git.current_branch(root),
        held=_held_elsewhere(root),
        left=(
            git.commits(root, f"{REMOTE_MAIN}..{branch}")
            if git.has_branch(root, branch)
            else None
        ),
    )
