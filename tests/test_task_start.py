"""`asdlc task start`: what it reads, and what it does with git.

The command reads once, decides, then acts. What it decides is tested on plain
data in `tests/domain/test_build.py`. The tests here are for the other two
parts, where git's own behaviour is the thing checked: `read_start` reads each
fact from the right place, and the command makes the branch, pushes, opens the
draft, and puts the checkout back when a step fails. They run on a clone whose
`origin` is a bare repository on disk, with a stand-in for `gh`, and reach no
network.
"""

import json
import sys

from click.testing import CliRunner

from asdlc.cli import cli, read_start
from asdlc.domain.build import Commit, Found
from asdlc.domain.tasks import Pull
from tests.conftest import (
    ACCEPTED,
    calls,
    commit_files,
    git,
    held_pulls,
    pull_row,
    second_clone,
    task_text,
    write_pulls,
)

ENDPOINT = "claims/01-endpoint"
PANEL = "claims/02-panel"
BRANCH = f"task/{ENDPOINT}"
SUBJECT = f"Start task {ENDPOINT}"
LINK = "https://example.invalid/pull/1"

PANEL_BRANCH = f"task/{PANEL}"
ELSEWHERE = "task/claims/09-elsewhere"
MERGED = "Merge pull request #4 from owner/task/claims/02-panel"
EXPORT_FILE = "intent/claims/tasks/03-export/task.md"
LATE_FILE = "intent/claims/tasks/04-late/task.md"
LOCAL_FILE = "intent/claims/tasks/05-local/task.md"


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


def test_a_start_reads_the_remote_as_last_fetched_and_the_checkout_it_is_in(remote, gh):
    # On the remote: main has moved on, with other checks and a task merged. A
    # tasks branch holds a task that is not merged, and a task's branch is there
    # with a draft pull request.
    other = second_clone(remote)
    git(other, "switch", "-q", "-c", PANEL_BRANCH)
    commit_files(other, {"panel.py": "refresh = 60\n"}, "the panel")
    git(other, "switch", "-q", "main")
    git(other, "merge", "-q", "--no-ff", "-m", MERGED, PANEL_BRANCH)
    moved = {".asdlc/checks": "just check\n", LATE_FILE: task_text(1, "R1", 1, "late")}
    commit_files(other, moved, "other checks, and one more task")
    git(other, "push", "-q", "origin", "main", f"main:{ELSEWHERE}")
    git(other, "switch", "-q", "-c", "tasks/claims")
    commit_files(other, {EXPORT_FILE: task_text(2, "R2", 3, "the export")}, "Tasks")
    git(other, "push", "-q", "origin", "tasks/claims")
    write_pulls(gh, pull_row(ELSEWHERE, 7, draft=True))

    # In this clone, whose own main is behind: a second worktree on a branch of
    # its own, a branch that a start left with its start commit, a task that
    # is committed here and nowhere else, and a file that is not committed.
    git(remote, "fetch", "-q", "--prune", "origin")
    tree = remote.parent / "tree"
    git(remote, "worktree", "add", "-q", "-b", PANEL_BRANCH, str(tree), "main")
    git(remote, "switch", "-q", "--no-track", "-c", BRANCH, "origin/main")
    git(remote, "commit", "-q", "--allow-empty", "-m", SUBJECT)
    left = git(remote, "rev-parse", "HEAD").strip()
    git(remote, "switch", "-q", "-c", "elsewhere", "main")
    commit_files(remote, {LOCAL_FILE: task_text(1, "R1", 1, "local")}, "cut here")
    (remote / "notes.txt").write_text("not committed\n")

    found = read_start(remote, ENDPOINT)

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
    panel = read_start(remote, "claims/02-panel")
    assert (panel.cut, panel.left) == (True, ())
    export = read_start(remote, "claims/03-export")
    assert (export.cut, export.left) == (True, None)
    local = read_start(remote, "claims/05-local")
    assert (local.cut, local.left) == (True, None)
    nothing = read_start(remote, "claims/09-nothing")
    assert (nothing.cut, nothing.left) == (False, None)

    # From the other worktree, this one is the worktree that is elsewhere.
    there = read_start(tree, ENDPOINT)
    assert (there.on, there.uncommitted) == (PANEL_BRANCH, ())
    assert there.held == {"elsewhere": str(remote)}
    assert (there.left, there.merges) == (found.left, found.merges)


def test_with_no_remote_a_start_reads_that_there_is_nothing_there(repository):
    missing = str(repository.parent / "no-such-program")
    git(repository, "config", "asdlc.gh", missing)

    found = read_start(repository, ENDPOINT)

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
    git(repository, "switch", "-q", "--detach", "main")
    assert read_start(repository, ENDPOINT).on == ""


def test_a_start_moves_the_checkout_to_a_branch_from_the_remotes_main_and_opens_a_draft(
    remote, gh
):
    other = second_clone(remote)
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


def test_when_the_draft_cannot_be_opened_the_start_is_undone_here_and_on_the_remote(
    remote, gh
):
    gh.fail.write_text("create\n")
    before = everything(remote, gh)

    failed(
        start(remote),
        "told to fail on create",
        "could not be opened",
        "the branch is off the remote again",
    )

    assert everything(remote, gh) == before
    assert len(opened(gh)) == 1


def test_when_the_remote_will_not_give_the_branch_up_it_is_left_and_a_resume_is_named(
    remote, gh
):
    # A remote that takes a new branch and refuses to delete one, as a
    # protected branch does. The branch here was left by an earlier start.
    hook = origin(remote) / "hooks" / "update"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(
        '#!/bin/sh\ncase "$3" in *[!0]*) exit 0 ;; esac\n'
        'echo "this remote keeps its branches" >&2\nexit 1\n'
    )
    hook.chmod(0o755)
    git(remote, "branch", "--no-track", BRANCH, "origin/main")
    gh.fail.write_text("create\n")

    failed(
        start(remote),
        "could not be opened",
        "could not be deleted from the remote, so it is left there",
        f"asdlc task start --resume {ENDPOINT}",
    )

    assert on(remote) == "main"
    assert git(remote, "status", "--porcelain") == ""
    assert git(remote, "log", "-1", "--format=%s", BRANCH).strip() == SUBJECT
    assert commit(origin(remote), BRANCH) == commit(remote, BRANCH)
    assert held_pulls(gh) == []


def racing(loser, winner, hook: str):
    """Have a git hook in `loser` run the whole of a start in `winner`, once.

    So the winner's start finishes after the loser's fetch and before its push
    is taken, which no second start run afterwards could show: that one is
    refused before it pushes. Give the file the winner's output goes to.
    """
    log = loser.parent / "the-other-start.log"
    run_it = f'"{sys.executable}" -c "from asdlc.cli import main; main()"'
    script = (
        "#!/bin/sh\n"
        f'[ -e "{log}" ] && exit 0\n'
        "unset $(git rev-parse --local-env-vars)\n"
        f'{run_it} task start {ENDPOINT} --root "{winner}" >"{log}" 2>&1\n'
        "exit 0\n"
    )
    path = loser / ".git" / "hooks" / hook
    path.parent.mkdir(exist_ok=True)
    path.write_text(script)
    path.chmod(0o755)
    return log


def lost_to(winner, loser, gh, done, log, how: str) -> None:
    """Check a start that lost: nothing of it is left, and it names the winner."""
    assert log.read_text() == f"{BRANCH}\t{LINK}\n"
    failed(
        done,
        f"another start claimed {ENDPOINT} first",
        how,
        f"Its pull request: {LINK}",
    )
    assert (on(loser), branches(loser)) == ("main", {"main"})
    assert git(loser, "status", "--porcelain") == ""
    assert commit(origin(loser), BRANCH) == commit(winner)
    assert commit(loser, f"origin/{BRANCH}") == commit(winner)
    assert held_pulls(gh) == [pull_row(BRANCH, 1, draft=True)]
    assert len(opened(gh)) == 1


def test_of_two_starts_at_one_instant_the_second_finds_the_branch_already_there(
    remote, gh, monkeypatch
):
    # Pinned to one instant, the two start commits are one commit, so the
    # second push is not refused: the remote answers that it is up to date.
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-11-18T12:00:00+00:00")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-11-18T12:00:00+00:00")
    winner = second_clone(remote)
    log = racing(remote, winner, "post-checkout")

    done = start(remote)

    lost_to(winner, remote, gh, done, log, "the remote had the branch already")


def test_a_start_that_another_overtakes_as_it_pushes_is_refused_by_the_remote(
    remote, gh
):
    winner = second_clone(remote)
    log = racing(remote, winner, "pre-push")

    done = start(remote)

    lost_to(winner, remote, gh, done, log, "the remote refused this one's push")


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
