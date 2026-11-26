"""Building a task: what a start reads, what it decides, and what a start left.

Nothing here touches git or GitHub. The facts are handed over as plain data,
once, in a `Found`. The functions here decide from it, and whoever called them
does what they answer.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from asdlc.domain.documents import Document
from asdlc.domain.tasks import Pull, State, Task, branch_of, stated

CHECKS = ".asdlc/checks"


@dataclass(frozen=True)
class Commit:
    """A commit, with the files it changed."""

    id: str
    subject: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class Found:
    """What a start reads before it decides, as plain data.

    It is read once, after the fetch. "The remote" is `origin`, as it was last
    fetched.
    """

    remote: bool  # the repository has a remote
    main: bool  # and the remote has a main
    pulls: tuple[Pull, ...] | None  # the open pull requests; None: not listed
    checks: str | None  # the checks file on the remote's main; None: no file
    uncommitted: tuple[str, ...]  # the paths with a change that is not committed
    texts: tuple[tuple[str, str], ...]  # the documents on the remote's main
    branches: frozenset[str]  # the remote's branches
    merges: tuple[str, ...]  # the subjects of the merges on the remote's main
    cut: bool  # the task's task.md is in the checkout, or on the remote's tasks/<slug>
    on: str  # the branch the checkout is on; empty when it is on none
    held: Mapping[str, str]  # each branch another worktree holds, and its folder
    # A local branch of the task's name: the commits it has and the remote's
    # main lacks. None when there is no such branch.
    left: tuple[Commit, ...] | None


class Stop(StrEnum):
    """Why a command stops before it has made anything."""

    REFUSED = "refused"  # it could tell it should not, or could not finish
    NO_TASK = "no task"  # the target matched nothing
    NO_MAIN = "no main"  # there is no main to start from


@dataclass(frozen=True)
class Refused:
    """A start that is not made, and the reason to give."""

    reason: str
    stop: Stop = Stop.REFUSED


@dataclass(frozen=True)
class Start:
    """What a start does, once nothing stands in its way."""

    task: Task
    reuse: bool  # switch to the branch a start that was cut short left
    started: bool  # that branch has its start commit already


def start_subject(id: str) -> str:
    """Give the subject of the empty commit that records when a task was started."""
    return f"Start task {id}"


def check_lines(text: str | None) -> tuple[str, ...]:
    """Give the command lines of a checks file, in order.

    A line that is empty or starts with `#` is no command line. A file with
    none counts as missing, and so does no file at all.
    """
    lines = (line.strip() for line in (text or "").splitlines())
    return tuple(line for line in lines if line and not line.startswith("#"))


def answer(porcelain: str, branch: str) -> str:
    """Give the one character a push answered for a branch; empty with no answer.

    `porcelain` is what `git push --porcelain` printed. `*` is a branch the
    push made, `=` one that was there already with this commit, and `!` a push
    the remote refused.
    """
    for line in porcelain.splitlines():
        flag, _, rest = line.partition("\t")
        pushed_to = rest.partition("\t")[0].rpartition(":")[2]
        if pushed_to == f"refs/heads/{branch}":
            return flag
    return ""


def claimed(porcelain: str, branch: str) -> bool:
    """Say whether a push made the branch on the remote.

    Only that is a claim. A branch that was there already, and a push the
    remote refused, claimed nothing.
    """
    return answer(porcelain, branch) == "*"


def lost_claim(id: str, flag: str, pulls: Sequence[Pull]) -> str:
    """Say why a start whose push claimed nothing is not a start.

    `flag` is what the push answered for the branch. `pulls` are the open pull
    requests, read after the push: when another start made the branch first,
    the reason gives that start's pull request.
    """
    branch = branch_of(id)
    if flag not in ("=", "!"):
        return f"the push did not make '{branch}' on the remote, so {id} is not started"
    how = "the remote had the branch already" if flag == "=" else "the remote refused"
    link = next((pull.link for pull in pulls if pull.branch == branch), "")
    theirs = f"Its pull request: {link}" if link else "It has no pull request yet"
    return f"another start claimed {id} first, and {how} this one's push. {theirs}"


def unopened(id: str, deleted: bool) -> str:
    """Say what became of a start whose pull request could not be opened.

    `deleted` says the branch was taken off the remote again.
    """
    branch = branch_of(id)
    if deleted:
        return (
            f"the pull request for '{branch}' could not be opened, so the start "
            f"is undone: the branch is off the remote again, and {id} is not started"
        )
    return (
        f"the pull request for '{branch}' could not be opened, and the branch "
        "could not be deleted from the remote, so it is left there. "
        f"`asdlc task start --resume {id}` finishes the start"
    )


def leftover(commits: Sequence[Commit], id: str) -> bool:
    """Say whether a local branch is what a start that was cut short left.

    `commits` are those the branch has and the remote's main lacks. It is a
    leftover when it holds none, or the task's start commit and nothing else.
    """
    return not commits or (len(commits) == 1 and has_start(commits, id))


def has_start(commits: Sequence[Commit], id: str) -> bool:
    """Say whether a branch's first commit is the task's empty start commit."""
    first = commits[0] if commits else None
    return first is not None and first.subject == start_subject(id) and not first.files


def _held_up(task: Task, known: Sequence[Task]) -> str:
    states = {other.id: other.state for other in known}
    waited = [id for id in task.depends if states.get(id) is not State.DONE]
    verb = "is" if len(waited) == 1 else "are"
    return f"it is waiting for {', '.join(waited)}, which {verb} not done"


def refusal(
    id: str,
    known: Sequence[Task],
    *,
    on: str = "",
    held: Mapping[str, str] | None = None,
) -> str | None:
    """Say why a task cannot be started; None when it can.

    `known` are the tasks on the remote's main, with their states as the remote
    alone gives them. A task that is not among them is one whose `task.md` is
    not merged yet: the caller has already found it somewhere. `on` is the
    branch the checkout is on. `held` gives the folder of the worktree for each
    branch another worktree of the clone has checked out.

    The reason reads after "cannot start <id>: ".
    """
    branch = branch_of(id)
    here = next((task for task in known if task.branch == on and task.id != id), None)
    if here is not None and here.state is State.CLAIMED:
        return (
            f"this checkout is on '{on}', where {here.id} is being built. "
            "Switch to another branch first, or start this task in another worktree"
        )
    if held and branch in held:
        return (
            f"its branch '{branch}' is checked out in another worktree: {held[branch]}"
        )
    task = next((task for task in known if task.id == id), None)
    if task is None:
        slug = id.split("/")[0]
        return f"it is not on main yet. It waits for the merge of 'tasks/{slug}'"
    if task.state is State.WAITING:
        return _held_up(task, known)
    if task.state in (State.CLAIMED, State.IN_REVIEW):
        if task.pull_request:
            return f"it is {task.state}. Its pull request: {task.pull_request}"
        return (
            f"it is {task.state} and has no pull request. "
            f"`asdlc task start --resume {id}` opens one"
        )
    if task.state is State.DONE:
        return "it is done: its branch was merged"
    return None


def _cannot_finish(found: Found) -> Refused | None:
    """Give the reason a start can tell beforehand that it could not finish."""
    if not found.remote:
        return Refused(
            "this repository has no remote named 'origin', so a task's branch has "
            "nowhere to be pushed"
        )
    if not found.main:
        return Refused("the remote has no main branch", Stop.NO_MAIN)
    if found.pulls is None:
        return Refused(
            "this repository's pull requests could not be listed, so one could "
            "not be opened. Is gh installed and signed in, and is 'origin' on GitHub?"
        )
    if not check_lines(found.checks):
        return Refused(
            f"the remote's main has no checks: {CHECKS} holds no command line "
            "there. Put the command lines in it, one to a line, and merge that first"
        )
    if found.uncommitted:
        return Refused(
            f"this checkout has uncommitted changes: {', '.join(found.uncommitted)}. "
            "Commit them or remove them first"
        )
    return None


def start(id: str, found: Found, documents: Sequence[Document]) -> Start | Refused:
    """Decide what `asdlc task start` does: the start, or why there is none.

    `documents` are `found.texts`, parsed. The reasons come in the order a
    person can act on them: first what the command could not finish with, then
    a target that names nothing, then the task and the branches themselves.
    """
    stopped = _cannot_finish(found)
    if stopped is not None:
        return stopped
    known = stated(documents, found.branches, found.pulls or (), found.merges)
    task = next((task for task in known if task.id == id), None)
    if task is None and not found.cut:
        slug = id.split("/")[0]
        return Refused(
            f"no task '{id}' on the remote's main, in this checkout or on the "
            f"remote's tasks/{slug}. List them: asdlc task list",
            Stop.NO_TASK,
        )
    reason = refusal(id, known, on=found.on, held=found.held)
    if reason is None and found.left is not None and not leftover(found.left, id):
        reason = (
            f"a local branch '{branch_of(id)}' holds {len(found.left)} commit(s) "
            "that no start made. Rename it or delete it first"
        )
    if reason is not None or task is None:
        return Refused(f"cannot start {id}: {reason}")
    return Start(
        task, reuse=found.left is not None, started=has_start(found.left or (), id)
    )
