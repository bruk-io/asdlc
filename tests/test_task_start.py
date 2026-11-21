"""`asdlc task start`, where git's own behaviour is the thing checked.

The command reads once, decides, then acts. What it decides is tested on plain
data in `tests/domain/test_build.py`, and what it reads in
`tests/io/test_checkout.py`. The tests here are for the acting: the branch it
makes, the push, the draft, and the checkout put back when a step fails. They
run on a clone whose `origin` is a bare repository on disk, with a stand-in for
`gh`, and reach no network.
"""

import json

from click.testing import CliRunner

from asdlc.cli import cli
from tests.conftest import (
    calls,
    commit_files,
    git,
    held_pulls,
    pull_row,
    second_clone,
)

ENDPOINT = "claims/01-endpoint"
PANEL = "claims/02-panel"
BRANCH = f"task/{ENDPOINT}"
SUBJECT = f"Start task {ENDPOINT}"
LINK = "https://example.invalid/pull/1"


def run(*args: object):
    return CliRunner().invoke(cli, [str(arg) for arg in args])


def start(root, id: str = ENDPOINT, *flags: str):
    return run("task", "start", id, *flags, "--root", root)


def on(root) -> str:
    return git(root, "branch", "--show-current").strip()


def commit(root, ref: str = "HEAD") -> str:
    return git(root, "rev-parse", ref).strip()


def branches(root) -> set[str]:
    return set(git(root, "branch", "--format=%(refname:short)").split())


def origin(root):
    return root.parent / "origin.git"


def everything(root, gh) -> tuple:
    """What a start that fails must leave as it was, here and on the remote."""
    return (
        on(root),
        commit(root),
        git(root, "status", "--porcelain"),
        git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"),
        git(origin(root), "for-each-ref", "--format=%(refname) %(objectname)"),
        held_pulls(gh),
    )


def opened(gh) -> list[list[str]]:
    return [call for call in calls(gh) if call[:2] == ["pr", "create"]]


def failed(done, *words: str) -> None:
    assert done.exit_code == 1, done.output
    assert done.stdout == ""
    for word in words:
        assert word in done.stderr, done.stderr


def test_a_start_moves_the_checkout_to_a_branch_from_the_remotes_main_and_opens_a_draft(
    remote, gh
):
    other = second_clone(remote)
    git(other, "config", "asdlc.gh", gh.program)
    commit_files(other, {"README.md": "claims\n"}, "main moves on")
    git(other, "push", "-q", "origin", "main")
    behind = commit(remote, "main")
    branch = f"task/{PANEL}"

    done = start(remote, PANEL)

    assert done.exit_code == 0, done.output
    assert done.stdout == f"{branch}\t{LINK}\n"

    # R1: on the task's branch, made from the remote's main and not the local one.
    assert on(remote) == branch
    assert commit(remote, "HEAD~1") == commit(other)
    assert commit(remote, "main") == behind
    assert git(remote, "status", "--porcelain") == ""

    # R2: one commit, which changes no file and records the start.
    assert git(remote, "rev-list", "--count", "origin/main..HEAD").strip() == "1"
    assert git(remote, "log", "-1", "--format=%s by %an").strip() == (
        f"Start task {PANEL} by Dana"
    )
    assert git(remote, "diff", "--name-only", "HEAD~1", "HEAD") == ""

    # R3: pushed under its own name, with a draft against main.
    assert commit(origin(remote), branch) == commit(remote)
    upstream = git(remote, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")
    assert upstream.strip() == f"origin/{branch}"
    assert held_pulls(gh) == [pull_row(branch, 1, draft=True)]
    (create,) = opened(gh)
    asked = dict(zip(create[3::2], create[4::2], strict=True))
    assert create[2] == "--draft"
    assert (asked["--base"], asked["--head"]) == ("main", branch)
    assert asked["--title"] == "Task: the panel"
    assert "`intent/claims/tasks/02-panel/task.md`" in asked["--body"]
    assert "- claims.R2" in asked["--body"]

    # The push is the claim: another clone reads the task as claimed.
    shown = json.loads(run("task", "show", PANEL, "--json", "--root", other).stdout)
    assert (shown["state"], shown["pull_request"]) == ("claimed", LINK)

    # The task's own plan is started on this branch, and makes no branch.
    planned = run("plan", "new", PANEL, "--root", remote)
    assert (planned.exit_code, planned.stdout.strip()) == (
        0,
        "intent/claims/tasks/02-panel/plan.md",
    )
    assert (on(remote), branches(remote)) == (branch, {"main", branch})


def test_a_start_in_a_linked_worktree_moves_that_worktree_and_not_the_main_checkout(
    remote, gh
):
    tree = remote.parent / "tree"
    git(remote, "worktree", "add", "-q", "-b", "worktree-one", tree, "origin/main")
    main = commit(remote, "origin/main")
    before = (on(remote), commit(remote), git(remote, "status", "--porcelain"))

    done = start(tree, ENDPOINT, "--json")

    assert done.exit_code == 0, done.output
    assert json.loads(done.stdout) == {"branch": BRANCH, "pull_request": LINK}
    assert on(tree) == BRANCH
    assert (commit(tree, "HEAD~1"), commit(tree, "worktree-one")) == (main, main)
    assert commit(origin(remote), BRANCH) == commit(tree)
    assert (on(remote), commit(remote), git(remote, "status", "--porcelain")) == before


def test_a_start_that_is_refused_says_why_and_makes_nothing(remote, gh):
    missing = start(remote, "claims/09-nothing")
    assert missing.exit_code == 3
    assert "no task 'claims/09-nothing'" in missing.stderr

    (remote / "notes.txt").write_text("not committed\n")
    before = everything(remote, gh)

    failed(start(remote), "uncommitted changes: notes.txt")

    assert everything(remote, gh) == before
    assert opened(gh) == []


def test_when_git_will_not_make_the_start_commit_the_checkout_is_put_back(
    remote, gh, monkeypatch
):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(remote, "config", "--unset", "user.name")
    git(remote, "config", "--unset", "user.email")
    git(remote, "config", "user.useConfigOnly", "true")
    git(remote, "switch", "-q", "-c", "elsewhere")
    before = everything(remote, gh)

    failed(start(remote), "user.name and user.email")

    assert everything(remote, gh) == before
    assert opened(gh) == []


def test_when_the_push_fails_the_checkout_is_put_back_on_the_commit_it_was_on(
    remote, gh
):
    git(remote, "config", "remote.origin.pushurl", str(remote.parent / "gone.git"))
    git(remote, "switch", "-q", "--detach", "main")
    before = everything(remote, gh)

    failed(start(remote), f"did not make '{BRANCH}' on the remote", "gone.git")

    assert everything(remote, gh) == before
    assert on(remote) == ""
    assert opened(gh) == []


def test_when_the_draft_cannot_be_opened_a_branch_that_was_there_before_is_kept(
    remote, gh
):
    git(remote, "branch", "--no-track", BRANCH, "origin/main")
    gh.fail.write_text("create\n")

    failed(start(remote), "told to fail on create", "could not be opened")

    assert on(remote) == "main"
    assert git(remote, "status", "--porcelain") == ""
    assert git(remote, "log", "-1", "--format=%s", BRANCH).strip() == SUBJECT
    assert held_pulls(gh) == []


def test_a_branch_a_start_left_is_used_again_with_the_start_commit_it_has(remote, gh):
    git(remote, "switch", "-q", "--no-track", "-c", BRANCH, "origin/main")
    git(remote, "commit", "-q", "--allow-empty", "-m", SUBJECT)
    left = commit(remote)

    done = start(remote)

    assert done.exit_code == 0, done.output
    assert (on(remote), commit(remote)) == (BRANCH, left)
    assert commit(origin(remote), BRANCH) == left
    assert held_pulls(gh) == [pull_row(BRANCH, 1, draft=True)]


def test_a_fetch_that_fails_starts_nothing(remote, gh):
    git(remote, "remote", "set-url", "origin", str(remote.parent / "gone.git"))

    failed(start(remote), "could not fetch from the remote")

    assert (on(remote), branches(remote)) == ("main", {"main"})
    assert calls(gh) == []


def test_a_remote_with_no_main_exits_as_a_repository_with_no_main_does(
    repository, tmp_path_factory
):
    empty = tmp_path_factory.mktemp("remote") / "empty.git"
    git(repository, "init", "-q", "--bare", "-b", "main", str(empty))
    git(repository, "remote", "add", "origin", str(empty))
    git(repository, "config", "asdlc.gh", str(empty.parent / "no-such-program"))

    done = start(repository)

    assert done.exit_code == 4
    assert "the remote has no main branch" in done.stderr
    assert branches(repository) == {"main"}


def test_a_root_below_the_top_and_a_target_that_is_no_task_are_bad_usage(repository):
    below = start(repository / "intent")
    assert (below.exit_code, "top of its checkout" in below.stderr) == (2, True)
    assert start(repository, "claims").exit_code == 2


def test_outside_a_repository_there_is_nothing_to_start(tmp_path):
    assert start(tmp_path).exit_code == 4
