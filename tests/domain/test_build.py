from dataclasses import replace

import pytest

from asdlc.domain.build import (
    Commit,
    Found,
    Refused,
    Resume,
    Start,
    Stop,
    answer,
    check_lines,
    claimed,
    has_start,
    leftover,
    lost_claim,
    refusal,
    resume,
    start,
    start_subject,
    unmerged,
    unopened,
)
from asdlc.domain.lint import library
from asdlc.domain.tasks import Pull, State, Task

BRANCH = "task/claims/01-endpoint"
LINK = "https://example.invalid/pull/7"


def task(name: str, state: State, **changes: object) -> Task:
    fields = dict(
        id=f"claims/{name}",
        slug="claims",
        name=name,
        title=name,
        step="1",
        size="2",
        delivers=("R1",),
        depends=(),
        branch=f"task/claims/{name}",
        has_plan=False,
        state=state,
    )
    return Task(**(fields | changes))


ENDPOINT = task("01-endpoint", State.READY)
PANEL = task("02-panel", State.READY)

START = Commit("a1", "Start task claims/01-endpoint", ())
WORK = Commit("b2", "the endpoint", ("api/status.py",))


def test_the_command_lines_of_a_checks_file_leave_out_comments_and_empty_lines():
    text = "# what every task has to pass\n\njust check\n  uv run pytest -q  \n#\n"
    assert check_lines(text) == ("just check", "uv run pytest -q")


@pytest.mark.parametrize("text", [None, "", "\n\n", "# just check\n", "   \n#\n"])
def test_a_checks_file_with_no_command_line_counts_as_missing(text):
    assert check_lines(text) == ()


def pushed(flag: str, summary: str, branch: str = BRANCH) -> str:
    ref = f"refs/heads/{branch}"
    return f"To /somewhere/origin.git\n{flag}\t{ref}:{ref}\t{summary}\nDone\n"


def test_a_push_that_made_the_branch_claimed_it():
    assert claimed(pushed("*", "[new branch]"), BRANCH) is True


@pytest.mark.parametrize(
    ("flag", "summary"),
    [
        ("=", "[up to date]"),
        ("!", "[rejected] (stale info)"),
        (" ", "a1b2c3d..e4f5a6b"),
        ("+", "a1b2c3d...e4f5a6b (forced update)"),
    ],
)
def test_a_push_that_did_not_make_the_branch_claimed_nothing(flag, summary):
    assert claimed(pushed(flag, summary), BRANCH) is False


def test_a_push_that_printed_no_line_for_the_branch_claimed_nothing():
    assert claimed("", BRANCH) is False
    assert claimed("To /somewhere/origin.git\nDone\n", BRANCH) is False
    other = pushed("*", "[new branch]", "task/claims/02-panel")
    assert claimed(other, BRANCH) is False
    assert claimed(other + pushed("=", "[up to date]"), BRANCH) is False


def test_what_a_push_answered_for_a_branch_is_its_one_character():
    assert answer(pushed("*", "[new branch]"), BRANCH) == "*"
    assert answer(pushed("=", "[up to date]"), BRANCH) == "="
    assert answer(pushed("!", "[rejected] (stale info)"), BRANCH) == "!"
    assert answer("To /somewhere/origin.git\nDone\n", BRANCH) == ""
    assert answer(pushed("*", "[new branch]", "task/claims/02-panel"), BRANCH) == ""


@pytest.mark.parametrize(
    ("flag", "how"),
    [("=", "the remote had the branch already"), ("!", "the remote refused")],
)
def test_a_start_that_lost_the_claim_names_the_pull_request_of_the_one_that_won(
    flag, how
):
    theirs = Pull(BRANCH, 7, LINK, True)
    other = Pull("task/claims/02-panel", 8, "https://example.invalid/pull/8", True)
    assert lost_claim("claims/01-endpoint", flag, (other, theirs)) == (
        f"another start claimed claims/01-endpoint first, and {how} this one's "
        f"push. Its pull request: {LINK}"
    )
    none_yet = lost_claim("claims/01-endpoint", flag, (other,))
    assert none_yet.endswith("this one's push. It has no pull request yet")


@pytest.mark.parametrize("flag", ["", " ", "+"])
def test_a_push_with_no_such_answer_is_not_put_down_to_another_start(flag):
    reason = lost_claim("claims/01-endpoint", flag, (Pull(BRANCH, 7, LINK, True),))
    assert reason == (
        f"the push did not make '{BRANCH}' on the remote, so claims/01-endpoint "
        "is not started"
    )


def test_a_start_whose_pull_request_could_not_be_opened_says_what_became_of_it():
    undone = unopened("claims/01-endpoint", deleted=True)
    assert f"the pull request for '{BRANCH}' could not be opened" in undone
    assert "the branch is off the remote again" in undone
    assert "claims/01-endpoint is not started" in undone
    assert "--resume" not in undone

    left = unopened("claims/01-endpoint", deleted=False)
    assert f"the pull request for '{BRANCH}' could not be opened" in left
    assert "could not be deleted from the remote, so it is left there" in left
    assert "`asdlc task start --resume claims/01-endpoint` finishes the start" in left


def test_a_branch_with_nothing_or_only_its_start_commit_is_a_leftover():
    assert start_subject("claims/01-endpoint") == START.subject
    assert leftover((), "claims/01-endpoint") is True
    assert leftover((START,), "claims/01-endpoint") is True
    assert has_start((), "claims/01-endpoint") is False
    assert has_start((START,), "claims/01-endpoint") is True


@pytest.mark.parametrize(
    "commits",
    [
        (WORK,),
        (START, WORK),
        (replace(START, subject="Start task claims/02-panel"),),
        (replace(START, files=("api/status.py",)),),
    ],
)
def test_a_branch_with_anything_else_on_it_is_no_leftover(commits):
    assert leftover(commits, "claims/01-endpoint") is False


def test_a_task_that_is_ready_can_be_started():
    assert refusal("claims/01-endpoint", (ENDPOINT, PANEL)) is None
    assert refusal("claims/01-endpoint", (ENDPOINT, PANEL), on="main", held={}) is None


def test_a_task_that_waits_names_what_it_waits_for():
    done = task("01-endpoint", State.DONE)
    late = task(
        "03-export",
        State.WAITING,
        depends=("claims/01-endpoint", "claims/02-panel", "claims/00-gone"),
    )
    reason = refusal(late.id, (done, PANEL, late))
    assert reason == (
        "it is waiting for claims/02-panel, claims/00-gone, which are not done"
    )
    one = replace(late, depends=("claims/02-panel",))
    assert refusal(one.id, (done, PANEL, one)) == (
        "it is waiting for claims/02-panel, which is not done"
    )


@pytest.mark.parametrize("state", [State.CLAIMED, State.IN_REVIEW])
def test_a_started_task_gives_its_pull_request_or_says_a_resume_opens_one(state):
    with_one = replace(ENDPOINT, state=state, pull_request=LINK)
    assert (
        refusal(ENDPOINT.id, (with_one,)) == f"it is {state}. Its pull request: {LINK}"
    )
    reason = refusal(ENDPOINT.id, (replace(ENDPOINT, state=state),))
    assert f"it is {state} and has no pull request" in reason
    assert "`asdlc task start --resume claims/01-endpoint` opens one" in reason


def test_a_task_that_is_done_is_not_started_again():
    reason = refusal(ENDPOINT.id, (replace(ENDPOINT, state=State.DONE),))
    assert reason == "it is done: its branch was merged"


def test_a_task_that_is_not_among_those_on_main_names_the_merge_it_waits_for():
    reason = refusal("claims/03-export", (ENDPOINT, PANEL))
    assert reason == "it is not on main yet. It waits for the merge of 'tasks/claims'"


def test_a_checkout_on_the_branch_of_another_task_that_is_claimed_is_refused():
    building = replace(ENDPOINT, state=State.CLAIMED, pull_request=LINK)
    reason = refusal(PANEL.id, (building, PANEL), on=BRANCH)
    assert f"this checkout is on '{BRANCH}'" in reason
    assert "claims/01-endpoint is being built" in reason
    assert "Switch to another branch" in reason
    assert "another worktree" in reason


@pytest.mark.parametrize("state", [State.READY, State.IN_REVIEW, State.DONE])
def test_a_checkout_on_the_branch_of_a_task_in_any_other_state_is_not(state):
    there = replace(ENDPOINT, state=state)
    assert refusal(PANEL.id, (there, PANEL), on=BRANCH) is None


def test_a_checkout_on_the_tasks_own_branch_gets_the_reason_for_its_state():
    mine = replace(ENDPOINT, state=State.CLAIMED, pull_request=LINK)
    assert refusal(ENDPOINT.id, (mine,), on=BRANCH) == (
        f"it is claimed. Its pull request: {LINK}"
    )
    assert refusal(ENDPOINT.id, (ENDPOINT,), on=BRANCH) is None


def test_a_branch_another_worktree_holds_is_refused_with_that_worktree():
    held = {BRANCH: "/work/trees/one", "main": "/work/claims"}
    reason = refusal(ENDPOINT.id, (ENDPOINT, PANEL), on="main", held=held)
    assert reason == (
        f"its branch '{BRANCH}' is checked out in another worktree: /work/trees/one"
    )
    assert refusal(PANEL.id, (ENDPOINT, PANEL), on="main", held=held) is None


def cut(step: int, requirement: str, title: str, depends: str = "") -> str:
    front = f"kind: task\nstep: {step}\ndelivers: [{requirement}]\n{depends}size: 2\n"
    return f"---\n{front}---\n# Task: {title}\n"


# What the remote's main holds: one intent, its spec, its plan and three tasks,
# the third of which waits for the first.
TEXTS = (
    (
        "intent/claims/intent.md",
        "---\nkind: intent\nauthor: a\n---\n# Intent: claims\n",
    ),
    (
        "intent/claims/spec.md",
        "---\nkind: spec\n---\n# Spec: claims\n### R1: a\n### R2: b\n",
    ),
    (
        "intent/claims/plan.md",
        "---\nkind: plan\n---\n# Plan: claims\n"
        "## Files that change\n- api/status.py (new)\n## Order of work\n"
        "### Step 1: the endpoint\n- delivers: R1\n"
        "### Step 2: the panel\n- delivers: R2\n",
    ),
    ("intent/claims/tasks/01-endpoint/task.md", cut(1, "R1", "the endpoint")),
    ("intent/claims/tasks/02-panel/task.md", cut(2, "R2", "the panel")),
    (
        "intent/claims/tasks/03-export/task.md",
        cut(2, "R2", "the export", "depends: [01-endpoint]\n"),
    ),
)
DOCUMENTS, FINDINGS = library(TEXTS)
MERGED = "Merge pull request #4 from owner/task/claims/01-endpoint"

# A start with nothing in its way: a remote with a main and checks, pull
# requests that can be listed, a clean checkout on main, and no branch yet.
CLEAR = Found(
    remote=True,
    main=True,
    pulls=(),
    checks="# what a task has to pass\njust check\n",
    uncommitted=(),
    texts=TEXTS,
    branches=frozenset({"main"}),
    merges=(),
    cut=True,
    on="main",
    held={},
    left=None,
    behind=False,
    merging=False,
    conflicts=(),
)


def decide(id: str = "claims/01-endpoint", **changes: object) -> Start | Refused:
    return start(id, replace(CLEAR, **changes), DOCUMENTS)


def refused(decided: Start | Refused, *words: str, stop: Stop = Stop.REFUSED) -> None:
    assert isinstance(decided, Refused), decided
    assert decided.stop is stop
    for word in words:
        assert word in decided.reason, decided.reason


def test_the_documents_these_decisions_are_made_from_lint_clean():
    assert FINDINGS == ()


def test_a_ready_task_with_nothing_in_its_way_is_started_on_a_new_branch():
    decided = decide()
    assert isinstance(decided, Start)
    assert (decided.reuse, decided.started) == (False, False)
    assert (decided.task.id, decided.task.branch, decided.task.title) == (
        "claims/01-endpoint",
        BRANCH,
        "the endpoint",
    )


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"remote": False}, ["no remote named 'origin'"]),
        ({"pulls": None}, ["pull requests could not be listed", "gh"]),
        ({"checks": None}, ["has no checks", ".asdlc/checks"]),
        ({"checks": "# nothing to run yet\n\n"}, ["has no checks", ".asdlc/checks"]),
        (
            {"uncommitted": ("notes.txt", "api/status.py")},
            ["uncommitted changes: notes.txt, api/status.py"],
        ),
    ],
)
def test_what_a_start_could_not_finish_with_is_refused_whatever_the_task(
    changes, words
):
    refused(decide(**changes), *words)
    refused(decide("claims/02-panel", **changes), *words)
    refused(decide("claims/09-nothing", cut=False, **changes), *words)


def test_a_remote_with_no_main_is_no_main_to_start_from():
    refused(decide(main=False), "the remote has no main", stop=Stop.NO_MAIN)


def test_of_several_reasons_the_first_in_this_order_is_the_one_given():
    wrong = {
        "remote": False,
        "main": False,
        "pulls": None,
        "checks": None,
        "uncommitted": ("notes.txt",),
        "cut": False,
    }
    order = [
        ("remote", True, "no remote"),
        ("main", True, "no main"),
        ("pulls", (), "could not be listed"),
        ("checks", "just check\n", "no checks"),
        ("uncommitted", (), "uncommitted changes"),
    ]
    for name, mended, words in order:
        decided = decide("claims/09-nothing", **wrong)
        assert isinstance(decided, Refused)
        assert words in decided.reason
        wrong[name] = mended
    refused(decide("claims/09-nothing", **wrong), "no task", stop=Stop.NO_TASK)


def test_a_target_that_is_found_nowhere_matches_nothing():
    decided = decide("claims/09-nothing", cut=False)
    refused(
        decided,
        "no task 'claims/09-nothing'",
        "the remote's tasks/claims",
        stop=Stop.NO_TASK,
    )


def test_a_task_that_is_cut_and_not_on_main_names_the_merge_it_waits_for():
    decided = decide("claims/09-late", cut=True)
    assert decided == Refused(
        "cannot start claims/09-late: it is not on main yet. "
        "It waits for the merge of 'tasks/claims'"
    )


@pytest.mark.parametrize(
    ("id", "changes", "words"),
    [
        (
            "claims/01-endpoint",
            {"branches": frozenset({"main", BRANCH})},
            ["it is claimed and has no pull request", "--resume claims/01-endpoint"],
        ),
        (
            "claims/01-endpoint",
            {"pulls": (Pull(BRANCH, 7, LINK, True),)},
            [f"it is claimed. Its pull request: {LINK}"],
        ),
        (
            "claims/01-endpoint",
            {"pulls": (Pull(BRANCH, 7, LINK, False),)},
            [f"it is in review. Its pull request: {LINK}"],
        ),
        ("claims/01-endpoint", {"merges": (MERGED,)}, ["it is done"]),
        (
            "claims/03-export",
            {},
            ["it is waiting for claims/01-endpoint, which is not done"],
        ),
    ],
)
def test_only_a_task_that_reads_as_ready_on_the_remote_is_started(id, changes, words):
    refused(decide(id, **changes), f"cannot start {id}: ", *words)


def test_a_task_is_ready_once_what_it_waits_for_is_merged():
    decided = decide("claims/03-export", merges=(MERGED,))
    assert isinstance(decided, Start)
    assert decided.task.id == "claims/03-export"


def test_on_the_branch_of_a_task_that_is_being_built_another_is_not_started():
    building = {"on": BRANCH, "pulls": (Pull(BRANCH, 7, LINK, True),)}
    refused(
        decide("claims/02-panel", **building),
        f"this checkout is on '{BRANCH}'",
        "claims/01-endpoint is being built",
        "another worktree",
    )
    in_review = {"on": BRANCH, "pulls": (Pull(BRANCH, 7, LINK, False),)}
    assert isinstance(decide("claims/02-panel", **in_review), Start)


def test_a_task_whose_branch_another_worktree_holds_is_not_started():
    refused(
        decide(held={BRANCH: "/work/trees/one"}, left=()),
        "checked out in another worktree: /work/trees/one",
    )
    assert isinstance(decide(held={"task/claims/02-panel": "/work/trees/one"}), Start)


def test_a_branch_a_start_left_is_used_again_and_keeps_its_start_commit():
    assert decide(left=()) == replace(decide(), reuse=True, started=False)
    assert decide(left=(START,)) == replace(decide(), reuse=True, started=True)


@pytest.mark.parametrize(("left", "count"), [((WORK,), 1), ((START, WORK), 2)])
def test_a_local_branch_with_work_on_it_is_not_used_and_is_named(left, count):
    refused(
        decide(left=left),
        f"a local branch '{BRANCH}' holds {count} commit(s) that no start made",
    )


def test_a_local_branch_does_not_make_its_task_read_as_claimed():
    assert isinstance(decide(left=(), on=BRANCH), Start)


def test_a_merge_in_progress_on_another_branch_does_not_change_what_a_start_does():
    assert decide(merging=True, conflicts=("api/status.py",)) == decide()


# A resume with nothing in its way: the task's branch is on the remote with a
# draft pull request, and this clone has no branch for it.
DRAFT = Pull(BRANCH, 7, LINK, True)
STARTED = replace(CLEAR, branches=frozenset({"main", BRANCH}), pulls=(DRAFT,))


def pick_up(id: str = "claims/01-endpoint", **changes: object) -> Resume | Refused:
    return resume(id, replace(STARTED, **changes), DOCUMENTS)


def test_a_started_task_with_no_local_branch_gets_one_at_the_remotes_commit():
    decided = pick_up()
    assert isinstance(decided, Resume)
    assert (decided.task.id, decided.task.branch) == ("claims/01-endpoint", BRANCH)
    assert (decided.reuse, decided.replace, decided.merge) == (False, True, False)
    assert decided.pull == DRAFT


@pytest.mark.parametrize("left", [(), (START,)])
def test_a_branch_a_start_left_is_replaced_by_the_remotes_and_nothing_is_merged(left):
    decided = pick_up(left=left, behind=True)
    assert isinstance(decided, Resume)
    assert (decided.reuse, decided.replace, decided.merge) == (True, True, False)


@pytest.mark.parametrize("behind", [True, False])
def test_a_local_branch_with_work_is_kept_and_merged_into_when_the_remote_has_more(
    behind,
):
    decided = pick_up(left=(START, WORK), behind=behind)
    assert isinstance(decided, Resume)
    assert (decided.reuse, decided.replace, decided.merge) == (True, False, behind)


def test_a_resume_is_told_which_pull_request_is_the_tasks_or_that_it_has_none():
    other = Pull("task/claims/02-panel", 8, "https://example.invalid/pull/8", False)
    ready = Pull(BRANCH, 7, LINK, False)

    lost = pick_up(pulls=(other,))
    assert isinstance(lost, Resume)
    assert lost.pull is None

    in_review = pick_up(pulls=(other, ready))
    assert isinstance(in_review, Resume)
    assert in_review.pull == ready


def test_a_resume_from_the_tasks_own_branch_is_not_refused_for_being_on_it():
    assert isinstance(pick_up(on=BRANCH, left=(START, WORK)), Resume)


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"remote": False}, ["no remote named 'origin'"]),
        ({"pulls": None}, ["pull requests could not be listed", "gh"]),
        ({"checks": None}, ["has no checks", ".asdlc/checks"]),
        (
            {"uncommitted": ("notes.txt", "api/status.py")},
            ["uncommitted changes: notes.txt, api/status.py"],
        ),
    ],
)
def test_a_resume_refuses_what_a_start_could_not_finish_with(changes, words):
    refused(pick_up(**changes), *words)
    refused(pick_up("claims/09-nothing", cut=False, **changes), *words)


def test_a_resume_with_no_main_on_the_remote_has_no_main_to_read():
    refused(pick_up(main=False), "the remote has no main", stop=Stop.NO_MAIN)


def test_a_resume_of_a_target_found_nowhere_matches_nothing():
    refused(
        pick_up("claims/09-nothing", cut=False),
        "no task 'claims/09-nothing'",
        stop=Stop.NO_TASK,
    )


@pytest.mark.parametrize(
    ("id", "changes", "words"),
    [
        (
            "claims/01-endpoint",
            {"branches": frozenset({"main"}), "pulls": ()},
            [
                f"it is not started: its branch '{BRANCH}' is not on the remote",
                "Start it: asdlc task start claims/01-endpoint",
            ],
        ),
        (
            "claims/03-export",
            {},
            ["it is not started: its branch 'task/claims/03-export' is not on"],
        ),
        ("claims/01-endpoint", {"merges": (MERGED,)}, ["it is done"]),
        (
            "claims/09-late",
            {"cut": True},
            ["it is not on main yet. It waits for the merge of 'tasks/claims'"],
        ),
        (
            "claims/02-panel",
            {"on": BRANCH, "branches": frozenset({"main", BRANCH, PANEL.branch})},
            [f"this checkout is on '{BRANCH}'", "claims/01-endpoint is being built"],
        ),
        (
            "claims/01-endpoint",
            {"held": {BRANCH: "/work/trees/one"}, "left": (START, WORK)},
            ["checked out in another worktree: /work/trees/one"],
        ),
    ],
)
def test_what_a_resume_refuses_and_the_reason_it_gives(id, changes, words):
    refused(pick_up(id, **changes), f"cannot resume {id}: ", *words)


def test_a_pull_request_for_a_branch_the_remote_has_not_got_is_no_start_to_resume():
    # A pull request from a fork names the fork's branch.
    decided = pick_up(branches=frozenset({"main"}))
    refused(decided, "cannot resume claims/01-endpoint: it is not started")


@pytest.mark.parametrize("state", [State.READY, State.WAITING])
def test_asked_about_a_resume_a_task_that_is_not_started_is_refused(state):
    there = replace(ENDPOINT, state=state)
    assert refusal(ENDPOINT.id, (there,), resume=True) == (
        f"it is not started: its branch '{BRANCH}' is not on the remote. "
        "Start it: asdlc task start claims/01-endpoint"
    )


@pytest.mark.parametrize("state", [State.CLAIMED, State.IN_REVIEW])
def test_asked_about_a_resume_a_started_task_is_not_refused(state):
    there = replace(ENDPOINT, state=state, pull_request=LINK)
    assert refusal(ENDPOINT.id, (there,), resume=True) is None
    assert refusal(ENDPOINT.id, (replace(there, pull_request=""),), resume=True) is None


def test_asked_about_a_resume_a_task_that_is_done_is_refused():
    there = replace(ENDPOINT, state=State.DONE)
    assert refusal(ENDPOINT.id, (there,), resume=True) == (
        "it is done: its branch was merged"
    )


def test_a_merge_in_progress_on_the_tasks_branch_is_answered_with_its_conflicts():
    files = ("api/status.py", "notes.txt")
    decided = pick_up(on=BRANCH, merging=True, conflicts=files, uncommitted=files)
    assert decided == Refused(
        f"a merge is in progress on '{BRANCH}', and 2 file(s) are in conflict. "
        "Resolve them, commit the merge, then run this again",
        files=files,
    )


def test_a_merge_with_no_file_left_in_conflict_is_to_be_committed():
    staged = ("api/status.py",)
    decided = pick_up(on=BRANCH, merging=True, conflicts=(), uncommitted=staged)
    assert decided == Refused(
        f"a merge is in progress on '{BRANCH}', and no file is left in conflict. "
        "Commit the merge, then run this again"
    )
    nothing_staged = pick_up(on=BRANCH, merging=True, conflicts=(), uncommitted=())
    assert nothing_staged == decided


def test_a_merge_in_progress_on_another_branch_is_an_uncommitted_change():
    files = ("api/status.py",)
    decided = pick_up(on="main", merging=True, conflicts=files, uncommitted=files)
    refused(decided, "uncommitted changes: api/status.py")
    assert decided.files == ()


def test_what_a_resume_could_not_finish_with_comes_before_a_merge_in_progress():
    decided = pick_up(on=BRANCH, merging=True, conflicts=("a.py",), checks=None)
    refused(decided, "has no checks")
    assert decided.files == ()


def test_a_merge_the_command_made_that_conflicts_says_where_it_came_from():
    reason = unmerged(BRANCH, ("api/status.py",), found=False)
    assert reason == (
        f"the remote's '{BRANCH}' did not merge into the local branch cleanly, "
        "and 1 file(s) are in conflict. Resolve them, commit the merge, then "
        "run this again"
    )
    none_left = unmerged(BRANCH, (), found=False)
    assert "and no file is left in conflict. Commit the merge" in none_left
