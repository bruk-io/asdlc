"""What is read from GitHub, and the stand-in for `gh` the other tests use."""

import subprocess

import pytest

from asdlc.io import files, github
from asdlc.io.github import Pull
from tests.conftest import calls, held_pulls, pull_row, write_pulls
from tests.conftest import git as run_git

DRAFT = "task/claims/01-endpoint"
READY = "task/claims/02-panel"


def fake_gh(folder, monkeypatch, script: str) -> None:
    files.write_program(folder / "gh", f"#!/bin/sh\n{script}\n")
    monkeypatch.setenv("PATH", f"{folder}:/usr/bin:/bin")


def stand_in(gh, *args: str, input: str | None = None):
    """Run the stand-in as asdlc runs it."""
    return subprocess.run(
        [str(gh.program), *args], capture_output=True, text=True, input=input
    )


def test_open_pull_requests_are_read_through_gh(
    repository, tmp_path_factory, monkeypatch
):
    rows = '[{"headRefName": "task/claims/01-a"}, {"headRefName": "spec/x"}]'
    fake_gh(tmp_path_factory.mktemp("bin"), monkeypatch, f"echo '{rows}'")
    assert github.program(repository) == "gh"
    assert github.open_pulls(repository) == (
        Pull("task/claims/01-a", 0, "", False),
        Pull("spec/x", 0, "", False),
    )


def test_gh_failing_or_missing_is_no_answer_not_an_empty_one(
    repository, tmp_path_factory, monkeypatch
):
    folder = tmp_path_factory.mktemp("bin")
    fake_gh(folder, monkeypatch, "exit 1")
    assert github.open_pulls(repository) is None
    monkeypatch.setenv("PATH", str(tmp_path_factory.mktemp("empty")))
    assert github.open_pulls(repository) is None


def test_gh_is_asked_for_the_open_pull_requests_with_their_draft_and_link(
    repository, tmp_path_factory, monkeypatch
):
    folder = tmp_path_factory.mktemp("bin")
    fake_gh(folder, monkeypatch, f'echo "$*" > {folder}/asked\necho "[]"')
    assert github.open_pulls(repository) == ()
    assert (folder / "asked").read_text().strip() == (
        "pr list --state open --limit 500 --json headRefName,isDraft,number,url"
    )


def test_each_open_pull_request_is_a_branch_a_number_a_link_and_draft_or_not(
    remote, gh
):
    write_pulls(gh, pull_row(DRAFT, 7, draft=True), pull_row(READY, 12))
    assert github.open_pulls(remote) == (
        Pull(DRAFT, 7, "https://example.invalid/pull/7", True),
        Pull(READY, 12, "https://example.invalid/pull/12", False),
    )


def test_the_program_the_key_names_is_run_in_place_of_gh(
    remote, gh, tmp_path_factory, monkeypatch
):
    rows = '[{"headRefName": "from/the/path"}]'
    fake_gh(tmp_path_factory.mktemp("bin"), monkeypatch, f"echo '{rows}'")
    write_pulls(gh, pull_row(DRAFT, 1, draft=True))

    assert github.program(remote) == str(gh.program)
    assert [pull.branch for pull in github.open_pulls(remote)] == [DRAFT]
    assert calls(gh)[-1][:2] == ["pr", "list"]

    run_git(remote, "config", "--unset", "asdlc.gh")
    assert [pull.branch for pull in github.open_pulls(remote)] == ["from/the/path"]


def test_a_program_the_key_names_that_is_missing_or_cannot_run_is_no_answer(remote, gh):
    gh.program.chmod(0o644)
    assert github.open_pulls(remote) is None
    run_git(remote, "config", "asdlc.gh", str(gh.program.parent / "no-such-program"))
    assert github.open_pulls(remote) is None


@pytest.mark.parametrize(
    "printed",
    ["not json", '{"headRefName": "a"}', '[{"number": 3}]', '["task/claims/01-a"]'],
)
def test_an_answer_that_is_not_the_list_asked_for_is_no_answer(
    repository, tmp_path_factory, monkeypatch, printed
):
    fake_gh(tmp_path_factory.mktemp("bin"), monkeypatch, f"echo '{printed}'")
    assert github.open_pulls(repository) is None


def test_the_stand_in_leaves_the_clones_working_tree_clean(remote, gh):
    assert github.open_pulls(remote) == ()
    stand_in(gh, "pr", "create", "--draft", "--head", DRAFT)
    assert run_git(remote, "status", "--porcelain") == ""
    for kept in (gh.program, gh.pulls, gh.calls, gh.fail):
        assert files.inside(kept, remote) is None


def test_the_stand_in_opens_a_draft_and_prints_its_link(remote, gh):
    opened = stand_in(
        gh,
        *("pr", "create", "--draft", "--base", "main", "--head", DRAFT),
        *("--title", "Task: the endpoint", "--body", "Builds\tthe task.\n\nR1\\R2\n"),
    )
    assert (opened.returncode, opened.stdout) == (0, "https://example.invalid/pull/1\n")
    assert held_pulls(gh) == [pull_row(DRAFT, 1, draft=True)]
    assert github.open_pulls(remote) == (Pull(DRAFT, 1, opened.stdout.strip(), True),)

    second = stand_in(gh, "pr", "create", "--base", "main", "--head", READY)
    assert second.stdout == "https://example.invalid/pull/2\n"
    assert held_pulls(gh) == [pull_row(DRAFT, 1, draft=True), pull_row(READY, 2)]

    again = stand_in(gh, "pr", "create", "--draft", "--head", DRAFT)
    assert (again.returncode, "already open" in again.stderr) == (1, True)
    assert len(held_pulls(gh)) == 2


def test_the_stand_in_marks_a_pull_request_ready_and_a_draft_again(gh):
    write_pulls(gh, pull_row(DRAFT, 3, draft=True), pull_row(READY, 13, draft=True))

    assert stand_in(gh, "pr", "ready", "3").returncode == 0
    assert held_pulls(gh) == [pull_row(DRAFT, 3), pull_row(READY, 13, draft=True)]

    assert stand_in(gh, "pr", "ready", "3", "--undo").returncode == 0
    assert held_pulls(gh)[0] == pull_row(DRAFT, 3, draft=True)

    assert stand_in(gh, "pr", "ready", "1").returncode == 1
    assert held_pulls(gh)[1] == pull_row(READY, 13, draft=True)


def test_the_stand_in_takes_a_comment_from_stdin(gh):
    write_pulls(gh, pull_row(DRAFT, 3, draft=True))
    body = "## Checks\n\n`just check`\texit 0\n\n```\nC:\\path\n286 passed\n```\n"

    added = stand_in(gh, "pr", "comment", "3", "--body-file", "-", input=body)
    assert added.returncode == 0
    assert calls(gh) == [["pr", "comment", "3", "--body-file", "-", body.rstrip("\n")]]
    assert held_pulls(gh) == [pull_row(DRAFT, 3, draft=True)]

    lost = stand_in(gh, "pr", "comment", "4", "--body-file", "-", input="late")
    assert (lost.returncode, "no open pull request 4" in lost.stderr) == (1, True)


def test_the_stand_in_records_each_call_on_one_line_with_its_arguments_as_given(gh):
    body = "Builds\tthe task.\n\nR1\\R2\\n\n"
    stand_in(gh, "pr", "list", "--state", "open")
    stand_in(
        gh, "pr", "create", "--draft", "--head", DRAFT, "--title", "", "--body", body
    )
    stand_in(gh, "pr", "ready", "1")

    assert gh.calls.read_text().count("\n") == 3
    assert calls(gh) == [
        ["pr", "list", "--state", "open"],
        ["pr", "create", "--draft", "--head", DRAFT, "--title", "", "--body", body],
        ["pr", "ready", "1"],
    ]


@pytest.mark.parametrize("subcommand", ["list", "create", "comment", "ready"])
def test_the_stand_in_fails_on_the_one_subcommand_it_is_told_to(gh, subcommand):
    write_pulls(gh, pull_row(READY, 1, draft=True))
    asked = {
        "list": ("pr", "list"),
        "create": ("pr", "create", "--draft", "--head", DRAFT),
        "comment": ("pr", "comment", "1", "--body-file", "-"),
        "ready": ("pr", "ready", "1"),
    }
    gh.fail.write_text(f"{subcommand}\n")

    for name, args in asked.items():
        done = stand_in(gh, *args, input="a comment")
        assert (done.returncode != 0) is (name == subcommand), name
        assert ("told to fail" in done.stderr) is (name == subcommand), name
    assert [call[1] for call in calls(gh)] == list(asked)

    gh.fail.unlink()
    assert stand_in(gh, *asked[subcommand], input="").returncode == 0


def test_the_stand_in_answers_nothing_it_was_not_built_for(gh):
    for args in (("pr", "merge", "1"), ("auth", "status"), ("pr",), ()):
        done = stand_in(gh, *args)
        assert (done.returncode, done.stdout) == (1, ""), args
    assert held_pulls(gh) == []


def test_a_draft_is_opened_against_main_and_its_link_is_what_comes_back(remote, gh):
    body = "Builds `intent/claims/tasks/01-endpoint/task.md`.\n\n- claims.R1\n"
    opened = github.open_draft(remote, DRAFT, "Task: the endpoint", body)

    assert (opened.ok, opened.out, opened.err) == (
        True,
        "https://example.invalid/pull/1",
        "",
    )
    assert held_pulls(gh) == [pull_row(DRAFT, 1, draft=True)]
    assert calls(gh) == [
        [
            *("pr", "create", "--draft", "--base", "main", "--head", DRAFT),
            *("--title", "Task: the endpoint", "--body", body),
        ]
    ]


def test_a_draft_that_cannot_be_opened_gives_what_the_program_said(remote, gh):
    gh.fail.write_text("create\n")
    failed = github.open_draft(remote, DRAFT, "Task: the endpoint", "a body")
    assert (failed.ok, failed.out) == (False, "")
    assert failed.err == "gh stand-in: told to fail on create"

    run_git(remote, "config", "asdlc.gh", str(gh.program.parent / "no-such-program"))
    missing = github.open_draft(remote, DRAFT, "Task: the endpoint", "a body")
    assert (missing.ok, missing.out) == (False, "")
    assert "could not be run" in missing.err


def test_a_program_that_opens_a_draft_and_prints_no_link_did_not_open_one(
    repository, tmp_path_factory, monkeypatch
):
    fake_gh(tmp_path_factory.mktemp("bin"), monkeypatch, "exit 0")
    opened = github.open_draft(repository, DRAFT, "Task: the endpoint", "a body")
    assert (opened.ok, opened.out, "no link" in opened.err) == (False, "", True)


def test_a_pull_request_is_marked_ready_and_made_a_draft_again(remote, gh):
    write_pulls(gh, pull_row(DRAFT, 3, draft=True))

    assert github.set_ready(remote, 3, ready=True).ok is True
    assert held_pulls(gh) == [pull_row(DRAFT, 3)]
    assert github.set_ready(remote, 3, ready=False).ok is True
    assert held_pulls(gh) == [pull_row(DRAFT, 3, draft=True)]
    assert calls(gh) == [["pr", "ready", "3"], ["pr", "ready", "3", "--undo"]]

    gone = github.set_ready(remote, 9, ready=True)
    assert (gone.ok, gone.err) == (False, "gh stand-in: no open pull request 9")
