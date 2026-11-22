"""`asdlc task start`: what it reads, and what it does with git.

The command reads once, decides, then acts. What it decides is tested on plain
data in `tests/domain/test_build.py`. The tests here are for the other two
parts, where git's own behaviour is the thing checked: `read_start` reads each
fact from the right place, and the command makes the branch, pushes, opens the
draft, and puts the checkout back when a step fails. With `--resume` it is the
branch the checkout ends up on, the merge of the remote's branch, and a merge
that is left in conflict. They run on a clone whose `origin` is a bare
repository on disk, with a stand-in for `gh`, and reach no network.
"""

import json
import subprocess
import sys

import pytest
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
        behind=False,
        merging=False,
        conflicts=(),
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


def resume(root, id: str = ENDPOINT, *flags: str):
    return start(root, id, "--resume", *flags)


def asked(gh) -> list[str]:
    """Give the subcommand of each call the stand-in took."""
    return [call[1] for call in calls(gh)]


def subjects(root) -> list[str]:
    """Give the subjects of what the checkout has and the remote's main lacks."""
    return git(root, "log", "--reverse", "--format=%s", "origin/main..HEAD").split(
        "\n"
    )[:-1]


def parents(root) -> int:
    return len(git(root, "log", "-1", "--format=%p").split())


def started(remote, gh, work: dict[str, str] | None = None, pull: bool | None = True):
    """Have another clone start the task, and give that clone.

    The remote gets the task's branch with its start commit, and `work` in one
    more commit when there is any. `pull` is whether its pull request is a
    draft, or None for a task that has lost its pull request.
    """
    other = second_clone(remote)
    git(other, "switch", "-q", "--no-track", "-c", BRANCH, "origin/main")
    git(other, "commit", "-q", "--allow-empty", "-m", SUBJECT)
    if work:
        commit_files(other, work, "the endpoint")
    git(other, "push", "-q", "origin", BRANCH)
    if pull is not None:
        write_pulls(gh, pull_row(BRANCH, 1, draft=pull))
    return other


def both_sides(remote, gh, mine: dict[str, str], theirs: dict[str, str], pushed=False):
    """Start the task here, then put a commit here and one on the remote.

    The one here is pushed only when `pushed` says so, and the one on the
    remote is another clone's, made on top of what was pushed. The checkout is
    left on main, and the task has a draft pull request. Give the other clone.
    """
    git(remote, "switch", "-q", "--no-track", "-c", BRANCH, "origin/main")
    git(remote, "commit", "-q", "--allow-empty", "-m", SUBJECT)
    git(remote, "push", "-q", "origin", BRANCH)
    commit_files(remote, mine, "mine")
    if pushed:
        git(remote, "push", "-q", "origin", BRANCH)
    git(remote, "switch", "-q", "main")
    other = second_clone(remote)
    git(other, "switch", "-q", BRANCH)
    commit_files(other, theirs, "theirs")
    git(other, "push", "-q", "origin", BRANCH)
    write_pulls(gh, pull_row(BRANCH, 1, draft=True))
    return other


WORK = {"api/status.py": "status = 'ok'\n"}
MINE = {"api/status.py": "status = 'mine'\n"}
THEIRS = {"api/status.py": "status = 'theirs'\n"}


def test_a_resume_in_a_clone_with_no_branch_for_the_task_makes_one_from_the_remotes(
    remote, gh
):
    other = started(remote, gh, WORK)
    main = commit(remote, "main")

    done = resume(remote)

    assert done.exit_code == 0, done.output
    assert done.stdout == f"{BRANCH}\t{LINK}\n"
    assert (on(remote), commit(remote)) == (BRANCH, commit(other))
    assert git(remote, "status", "--porcelain") == ""
    assert (remote / "api" / "status.py").read_text() == WORK["api/status.py"]
    assert commit(remote, "main") == main
    # It has a draft already, so none is opened and none is changed.
    assert asked(gh) == ["list"]


def test_a_branch_left_by_a_start_that_was_cut_short_is_replaced_by_the_remotes(
    remote, gh
):
    git(remote, "switch", "-q", "--no-track", "-c", BRANCH, "origin/main")
    git(
        remote,
        "-c",
        "user.name=cut short",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        SUBJECT,
    )
    left = commit(remote)
    git(remote, "switch", "-q", "main")
    other = started(remote, gh, WORK)
    assert left != commit(other, "HEAD~1")

    done = resume(remote)

    assert done.exit_code == 0, done.output
    assert (on(remote), commit(remote)) == (BRANCH, commit(other))
    assert subjects(remote) == [SUBJECT, "the endpoint"]
    assert left not in git(remote, "rev-list", "HEAD").split()


def test_a_resume_from_the_tasks_own_branch_leaves_the_checkout_there(remote, gh):
    other = started(remote, gh, WORK)
    here = commit(other)

    done = resume(other, ENDPOINT, "--json")

    assert done.exit_code == 0, done.output
    assert json.loads(done.stdout) == {"branch": BRANCH, "pull_request": LINK}
    assert (on(other), commit(other)) == (BRANCH, here)
    assert git(other, "status", "--porcelain") == ""
    assert asked(gh) == ["list"]


def test_a_started_task_that_lost_its_pull_request_gets_a_draft_opened(remote, gh):
    started(remote, gh, WORK, pull=None)

    done = resume(remote)

    assert done.exit_code == 0, done.output
    assert done.stdout == f"{BRANCH}\t{LINK}\n"
    assert held_pulls(gh) == [pull_row(BRANCH, 1, draft=True)]
    (create,) = opened(gh)
    wanted = dict(zip(create[3::2], create[4::2], strict=True))
    assert create[2] == "--draft"
    assert (wanted["--base"], wanted["--head"]) == ("main", BRANCH)
    assert wanted["--title"] == "Task: the endpoint"


def test_a_pull_request_that_was_ready_is_made_a_draft_again(remote, gh):
    started(remote, gh, WORK, pull=False)
    shown = json.loads(run("task", "show", ENDPOINT, "--json", "--root", remote).stdout)
    assert shown["state"] == "in review"

    done = resume(remote)

    assert done.exit_code == 0, done.output
    assert done.stdout == f"{BRANCH}\t{LINK}\n"
    assert held_pulls(gh) == [pull_row(BRANCH, 1, draft=True)]
    assert calls(gh)[-1] == ["pr", "ready", "1", "--undo"]
    assert opened(gh) == []
    shown = json.loads(run("task", "show", ENDPOINT, "--json", "--root", remote).stdout)
    assert shown["state"] == "claimed"


def test_a_local_branch_that_is_behind_the_remotes_is_brought_up(remote, gh):
    other = both_sides(remote, gh, {"mine.py": "mine = 1\n"}, WORK, pushed=True)
    behind = commit(remote, BRANCH)

    done = resume(remote)

    assert done.exit_code == 0, done.output
    assert (on(remote), commit(remote)) == (BRANCH, commit(other))
    assert commit(remote, "HEAD~1") == behind
    assert parents(remote) == 1


def test_with_a_commit_on_each_side_the_remotes_branch_is_merged_and_a_push_is_taken(
    remote, gh
):
    other = both_sides(remote, gh, {"mine.py": "mine = 1\n"}, WORK)
    mine = commit(remote, BRANCH)
    git(remote, "fetch", "-q", "origin")
    before = read_start(remote, ENDPOINT)
    assert (before.behind, before.merging, before.conflicts) == (True, False, ())

    done = resume(remote)

    assert done.exit_code == 0, done.output
    assert done.stdout == f"{BRANCH}\t{LINK}\n"
    assert on(remote) == BRANCH
    assert {commit(remote, "HEAD^1"), commit(remote, "HEAD^2")} == {mine, commit(other)}
    assert (remote / "mine.py").is_file()
    assert (remote / "api" / "status.py").is_file()
    assert git(remote, "status", "--porcelain") == ""
    assert read_start(remote, ENDPOINT).behind is False

    git(remote, "push", "-q", "origin", BRANCH)
    assert commit(origin(remote), BRANCH) == commit(remote)


def test_a_merge_that_conflicts_is_left_with_its_files_printed_and_the_draft_made(
    remote, gh
):
    both_sides(remote, gh, MINE, THEIRS)
    write_pulls(gh, pull_row(BRANCH, 1, draft=False))
    mine = commit(remote, BRANCH)

    done = resume(remote)

    assert done.exit_code == 1, done.output
    assert done.stdout == "api/status.py\n"
    assert "did not merge into the local branch cleanly" in done.stderr
    assert "1 file(s) are in conflict" in done.stderr
    # The merge is left as git left it, on the task's branch.
    assert (on(remote), commit(remote)) == (BRANCH, mine)
    assert commit(remote, "MERGE_HEAD") == commit(remote, f"origin/{BRANCH}")
    # Both sides added the file, which git marks `AA`.
    assert git(remote, "status", "--porcelain") == "AA api/status.py\n"
    # The pull request was made a draft before the merge, so the task reads
    # as claimed while the conflict is open.
    assert held_pulls(gh) == [pull_row(BRANCH, 1, draft=True)]
    found = read_start(remote, ENDPOINT)
    assert (found.merging, found.conflicts) == (True, ("api/status.py",))


def test_a_merge_in_progress_is_answered_until_it_is_committed(remote, gh):
    both_sides(remote, gh, MINE, THEIRS)
    git(remote, "fetch", "-q", "origin")
    git(remote, "switch", "-q", BRANCH)
    with pytest.raises(subprocess.CalledProcessError):
        git(remote, "merge", "-q", "--no-edit", f"origin/{BRANCH}")
    before = everything(remote, gh)

    # In conflict: the files are printed, and it is not an uncommitted change.
    done = resume(remote)
    assert done.exit_code == 1, done.output
    assert done.stdout == "api/status.py\n"
    assert f"a merge is in progress on '{BRANCH}'" in done.stderr
    assert "1 file(s) are in conflict" in done.stderr
    assert "uncommitted" not in done.stderr
    assert json.loads(resume(remote, ENDPOINT, "--json").stdout) == ["api/status.py"]
    assert everything(remote, gh) == before
    assert commit(remote, "MERGE_HEAD") == commit(remote, f"origin/{BRANCH}")

    # Resolved and not committed: nothing is printed, and it says to commit.
    (remote / "api" / "status.py").write_text("status = 'both'\n")
    git(remote, "add", "api/status.py")
    done = resume(remote)
    assert done.exit_code == 1, done.output
    assert done.stdout == ""
    assert "no file is left in conflict. Commit the merge" in done.stderr
    assert commit(remote, "MERGE_HEAD") == commit(remote, f"origin/{BRANCH}")

    # Committed: the resume goes through, with nothing left to merge.
    git(remote, "commit", "-q", "--no-edit")
    merged = commit(remote)
    done = resume(remote)
    assert done.exit_code == 0, done.output
    assert done.stdout == f"{BRANCH}\t{LINK}\n"
    assert (on(remote), commit(remote), parents(remote)) == (BRANCH, merged, 2)


def test_a_resume_that_is_refused_says_why_and_changes_nothing(remote, gh):
    started(remote, gh, WORK)
    git(remote, "fetch", "-q", "origin")
    tree = remote.parent / "tree"
    git(remote, "worktree", "add", "-q", str(tree), BRANCH)
    before = everything(remote, gh), everything(tree, gh)

    failed(
        resume(remote),
        f"cannot resume {ENDPOINT}",
        f"checked out in another worktree: {tree}",
    )
    failed(resume(remote, PANEL), f"cannot resume {PANEL}: it is not started")

    assert (everything(remote, gh), everything(tree, gh)) == before
    assert asked(gh) == ["list", "list"]


@pytest.mark.parametrize(
    ("fails", "pull", "words"),
    [
        ("create", None, ["could not be opened", f"{ENDPOINT} still has none"]),
        ("ready", False, ["could not be made a draft again", "still in review"]),
    ],
)
def test_when_the_pull_request_cannot_be_made_a_draft_the_checkout_is_put_back(
    remote, gh, fails, pull, words
):
    started(remote, gh, WORK, pull=pull)
    gh.fail.write_text(f"{fails}\n")
    git(remote, "switch", "-q", "--detach", "main")
    before = everything(remote, gh)

    failed(resume(remote), f"told to fail on {fails}", *words)

    # Back on the commit it was on, and the branch this run made is gone. The
    # remote's branch is another start's, and is left.
    assert everything(remote, gh) == before
    assert on(remote) == ""
    assert commit(origin(remote), BRANCH) != commit(remote)


def test_a_resume_that_fails_keeps_a_local_branch_it_did_not_make(remote, gh):
    both_sides(remote, gh, {"mine.py": "mine = 1\n"}, WORK)
    write_pulls(gh)
    gh.fail.write_text("create\n")
    before = everything(remote, gh)

    failed(resume(remote), "could not be opened")

    assert everything(remote, gh) == before
    assert (on(remote), BRANCH in branches(remote)) == ("main", True)


def test_when_git_will_not_make_the_merge_the_checkout_is_put_back(
    remote, gh, monkeypatch
):
    both_sides(remote, gh, {"mine.py": "mine = 1\n"}, WORK)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(remote, "config", "--unset", "user.name")
    git(remote, "config", "--unset", "user.email")
    git(remote, "config", "user.useConfigOnly", "true")
    before = everything(remote, gh)

    failed(resume(remote), "git would not merge", "user.name and user.email")

    # No merge is left to finish, so this is a failure like any other.
    assert everything(remote, gh) == before
    assert on(remote) == "main"
