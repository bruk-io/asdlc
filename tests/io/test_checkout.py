"""What a start reads, read from a real clone with a bare repository as `origin`.

One test sets up a clone where every fact has something to say, and checks each
is read from the right place. What is decided from the facts is tested on plain
data in `tests/domain/test_build.py`.
"""

from asdlc.domain.build import Commit, Found
from asdlc.domain.tasks import Pull
from asdlc.io import checkout
from tests.conftest import (
    ACCEPTED,
    commit_files,
    pull_row,
    second_clone,
    task_text,
    write_pulls,
)
from tests.conftest import git as run_git

ENDPOINT = "claims/01-endpoint"
BRANCH = "task/claims/01-endpoint"
PANEL_BRANCH = "task/claims/02-panel"
ELSEWHERE = "task/claims/09-elsewhere"
SUBJECT = "Start task claims/01-endpoint"
MERGED = "Merge pull request #4 from owner/task/claims/02-panel"
EXPORT_FILE = "intent/claims/tasks/03-export/task.md"
LATE_FILE = "intent/claims/tasks/04-late/task.md"
LOCAL_FILE = "intent/claims/tasks/05-local/task.md"


def test_a_start_reads_the_remote_as_last_fetched_and_the_checkout_it_is_in(remote, gh):
    # On the remote: main has moved on, with other checks and a task merged. A
    # tasks branch holds a task that is not merged, and a task's branch is there
    # with a draft pull request.
    other = second_clone(remote)
    run_git(other, "switch", "-q", "-c", PANEL_BRANCH)
    commit_files(other, {"panel.py": "refresh = 60\n"}, "the panel")
    run_git(other, "switch", "-q", "main")
    run_git(other, "merge", "-q", "--no-ff", "-m", MERGED, PANEL_BRANCH)
    moved = {".asdlc/checks": "just check\n", LATE_FILE: task_text(1, "R1", 1, "late")}
    commit_files(other, moved, "other checks, and one more task")
    run_git(other, "push", "-q", "origin", "main", f"main:{ELSEWHERE}")
    run_git(other, "switch", "-q", "-c", "tasks/claims")
    commit_files(other, {EXPORT_FILE: task_text(2, "R2", 3, "the export")}, "Tasks")
    run_git(other, "push", "-q", "origin", "tasks/claims")
    write_pulls(gh, pull_row(ELSEWHERE, 7, draft=True))

    # In this clone, whose own main is behind: a second worktree on a branch of
    # its own, a branch that a start left with its start commit, a task that
    # is committed here and nowhere else, and a file that is not committed.
    run_git(remote, "fetch", "-q", "--prune", "origin")
    tree = remote.parent / "tree"
    run_git(remote, "worktree", "add", "-q", "-b", PANEL_BRANCH, str(tree), "main")
    run_git(remote, "switch", "-q", "--no-track", "-c", BRANCH, "origin/main")
    run_git(remote, "commit", "-q", "--allow-empty", "-m", SUBJECT)
    left = run_git(remote, "rev-parse", "HEAD").strip()
    run_git(remote, "switch", "-q", "-c", "elsewhere", "main")
    commit_files(remote, {LOCAL_FILE: task_text(1, "R1", 1, "local")}, "cut here")
    (remote / "notes.txt").write_text("not committed\n")

    found = checkout.found(remote, ENDPOINT)

    assert (found.remote, found.main) == (True, True)
    assert found.pulls == (Pull(ELSEWHERE, 7, "https://example.invalid/pull/7", True),)
    assert found.checks == "just check\n"
    assert (remote / ".asdlc" / "checks").read_text() == "echo checked\n"
    assert found.uncommitted == ("notes.txt",)
    on_main = [path for path in ACCEPTED if path.endswith(".md")] + [LATE_FILE]
    assert [path for path, _ in found.texts] == sorted(on_main)
    assert found.branches == {"main", "tasks/claims", ELSEWHERE}
    assert found.merges == (MERGED,)
    assert found.on == "elsewhere"
    assert found.held == {PANEL_BRANCH: str(tree)}
    assert found.left == (Commit(left, SUBJECT, ()),)

    # Where the task's document is, and whether a local branch has its name.
    assert found.cut is True
    panel = checkout.found(remote, "claims/02-panel")
    assert (panel.cut, panel.left) == (True, ())
    export = checkout.found(remote, "claims/03-export")
    assert (export.cut, export.left) == (True, None)
    local = checkout.found(remote, "claims/05-local")
    assert (local.cut, local.left) == (True, None)
    nothing = checkout.found(remote, "claims/09-nothing")
    assert (nothing.cut, nothing.left) == (False, None)

    # From the other worktree, this one is the worktree that is elsewhere.
    there = checkout.found(tree, ENDPOINT)
    assert (there.on, there.uncommitted) == (PANEL_BRANCH, ())
    assert there.held == {"elsewhere": str(remote)}
    assert (there.left, there.merges) == (found.left, found.merges)


def test_with_no_remote_a_start_reads_that_there_is_nothing_there(repository):
    missing = str(repository.parent / "no-such-program")
    run_git(repository, "config", "asdlc.gh", missing)

    found = checkout.found(repository, ENDPOINT)

    assert found == Found(
        remote=False,
        main=False,
        pulls=None,
        checks=None,
        uncommitted=(),
        texts=(),
        branches=frozenset(),
        merges=(),
        cut=False,
        on="main",
        held={},
        left=None,
    )
    run_git(repository, "switch", "-q", "--detach", "main")
    assert checkout.found(repository, ENDPOINT).on == ""
