"""The command end to end: real files and a real git repository, run in process.

The grammar is `asdlc <noun> <verb> [target] [flags]`.
"""

import json

import pytest
from click.testing import CliRunner

from asdlc.cli import cli
from tests.conftest import (
    ACCEPTED,
    calls,
    commit_files,
    git,
    pull_row,
    second_clone,
    task_text,
    write_pulls,
)


def run(*args: object, input: str | None = None):
    return CliRunner().invoke(cli, [str(arg) for arg in args], input=input)


def test_the_bare_program_lists_the_nouns_and_a_bare_noun_its_verbs():
    for noun in ("branch", "document", "hook", "requirement"):
        assert noun in run().output
    assert "list" in run("requirement").output
    assert "show" in run("requirement").output


@pytest.mark.parametrize("help_flag", ["-h", "--help"])
def test_help_works_on_the_program_and_on_any_command(help_flag):
    assert run(help_flag).exit_code == 0
    assert "id, state, title" in run("requirement", "list", help_flag).output


def test_version_prints_the_version_alone():
    done = run("version")
    assert (done.exit_code, done.stdout.strip()) == (0, "2.0.0.dev0")


def test_document_check_prints_nothing_when_clean(example):
    done = run("document", "check", "--root", example)
    assert (done.exit_code, done.stdout) == (0, "")


def test_verbose_puts_diagnostics_on_stderr_only(example):
    done = run("document", "check", "--root", example, "-v")
    assert (done.stdout, "read 11 documents" in done.stderr) == ("", True)


def broken(repository):
    (repository / "intent" / "claims" / "spec.md").write_text("---\nkind: plan\n---\n")
    return repository


def test_document_check_fails_with_one_finding_per_line(repository):
    done = run("document", "check", "--root", broken(repository))
    assert done.exit_code == 1
    path, rule, message = done.stdout.strip().split("\t")
    assert (path, rule) == ("intent/claims/spec.md", "kind")
    assert "kind: spec" in message


def test_document_check_as_json_and_as_identifiers(repository):
    found = json.loads(
        run("document", "check", "--json", "--root", broken(repository)).stdout
    )
    assert [(f["path"], f["rule"]) for f in found] == [
        ("intent/claims/spec.md", "kind")
    ]
    quiet = run("document", "check", "-q", "--root", repository)
    assert quiet.stdout.strip() == "intent/claims/spec.md"


def test_document_check_takes_one_intent_as_its_target(example):
    assert run("document", "check", "claims-status", "--root", example).exit_code == 0
    done = run("document", "check", "nothing", "--root", example)
    assert done.exit_code == 3
    assert "no intent 'nothing'" in done.stderr
    assert "claims-status" in done.stderr


def test_requirement_list_is_what_is_in_force_unless_asked(example):
    lines = run("requirement", "list", "--root", example).stdout.strip().split("\n")
    assert "claims-status.R3" not in {line.split("\t")[0] for line in lines}
    assert all(len(line.split("\t")) == 3 for line in lines)
    everything = run("requirement", "list", "--all", "--root", example).stdout
    assert "claims-status.R3\treplaced\tStatus refreshes" in everything


def test_flags_may_come_before_or_after(example):
    after = run("requirement", "list", "--root", example, "--all").stdout
    before = run("requirement", "list", "--all", "--root", example).stdout
    assert after == before


def test_requirement_list_quiet_is_identifiers_and_json_is_one_array(example):
    ids = run("requirement", "list", "-q", "--root", example).stdout.split()
    assert "live-status.R1" in ids
    rows = json.loads(run("requirement", "list", "--json", "--root", example).stdout)
    assert {row["id"] for row in rows} == set(ids)
    assert (
        json.loads(run("requirement", "list", "--json", "-q", "--root", example).stdout)
        == ids
    )


def test_requirement_show_gives_one_in_full_with_its_lineage(example):
    done = run("requirement", "show", "live-status.R1", "--root", example)
    assert done.exit_code == 0
    lines = done.stdout.strip().split("\n")
    assert lines[0] == "id\tlive-status.R1"
    assert lines[-2:] == ["lineage\tclaims-status.R3", "lineage\tlive-status.R1"]
    document = json.loads(
        run("requirement", "show", "live-status.R1", "--json", "--root", example).stdout
    )
    assert document["lineage"] == ["claims-status.R3", "live-status.R1"]


def test_a_requirement_that_matches_nothing_is_status_3(example):
    done = run("requirement", "show", "nothing.R1", "--root", example)
    assert (done.exit_code, done.stdout) == (3, "")
    assert done.stderr.startswith("Error: no requirement 'nothing.R1'")
    assert "<intent>.R<number>" in done.stderr


def test_bad_usage_is_status_2(example):
    assert run("requirement", "show", "--root", example).exit_code == 2
    assert run("requirement", "list", "--nonsense").exit_code == 2
    assert run("requirement", "list", "one", "two").exit_code == 2


def spec_and_code(repository):
    git(repository, "switch", "-q", "-c", "spec/claims")
    (repository / "intent" / "claims" / "spec.md").write_text("---\nkind: spec\n---\n")
    (repository / "app.py").write_text("print('too early')\n")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "spec and code")
    return repository


def test_branch_check_judges_the_current_branch(repository):
    done = run("branch", "check", "--root", spec_and_code(repository))
    assert done.exit_code == 1
    verdict, path, reason = done.stdout.strip().split("\t")
    assert (verdict, path) == ("deny", "app.py")
    assert reason.startswith("this branch adds a spec")


def test_branch_check_takes_a_branch_as_its_target(repository):
    spec_and_code(repository)
    git(repository, "switch", "-q", "main")
    assert run("branch", "check", "--root", repository).stdout == ""
    named = run("branch", "check", "spec/claims", "--json", "--root", repository)
    assert named.exit_code == 1
    assert [r["path"] for r in json.loads(named.stdout)] == ["app.py"]


def test_a_branch_that_matches_nothing_is_status_3(repository):
    done = run("branch", "check", "nothing", "--root", repository)
    assert (done.exit_code, "no branch 'nothing'" in done.stderr) == (3, True)


def test_no_repository_is_status_4(tmp_path):
    done = run("branch", "check", "--root", tmp_path)
    assert done.exit_code == 4
    assert "not a git repository with a main branch" in done.stderr


def test_branch_new_starts_a_branch_and_prints_its_name(repository):
    done = run("branch", "new", "spec/claims", "--root", repository)
    assert (done.exit_code, done.stdout.strip()) == (0, "spec/claims")
    assert git(repository, "branch", "--show-current").strip() == "spec/claims"


def test_branch_new_refuses_until_what_it_builds_on_is_merged(repository):
    done = run("branch", "new", "plan/claims", "--root", repository)
    assert (done.exit_code, done.stdout) == (1, "")
    assert "intent/claims/spec.md is not on main yet" in done.stderr
    assert git(repository, "branch", "--show-current").strip() == "main"


def test_branch_new_says_so_when_git_refuses(repository):
    run("branch", "new", "spec/claims", "--root", repository)
    done = run("branch", "new", "spec/claims", "--root", repository)
    assert (done.exit_code, "already exist" in done.stderr) == (1, True)


def guard_hook(cwd, command: str) -> dict:
    payload = {"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": command}}
    done = run("hook", "run", "guard", input=json.dumps(payload))
    assert done.exit_code == 0, done.output
    return json.loads(done.stdout) if done.stdout else {}


def test_the_guard_hook_refuses_a_push_the_guard_denies(repository):
    spec_and_code(repository)
    denied = guard_hook(repository, "git push origin spec/claims")["hookSpecificOutput"]
    assert denied["permissionDecision"] == "deny"
    assert "- app.py: this branch adds a spec" in denied["permissionDecisionReason"]


def test_the_guard_hook_follows_git_dash_c_to_the_repository(
    repository, tmp_path_factory
):
    spec_and_code(repository)
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    assert guard_hook(elsewhere, "git push") == {}
    assert "hookSpecificOutput" in guard_hook(elsewhere, f"git -C {repository} push")


def test_the_guard_hook_is_silent_for_an_allowed_push_and_for_other_commands(
    repository,
):
    assert guard_hook(repository, "git push origin main") == {}
    spec_and_code(repository)
    assert guard_hook(repository, "git status") == {}
    assert guard_hook(repository, "git commit -m 'git push later'") == {}


def lint_hook(repository, file) -> dict:
    payload = {
        "tool_name": "Write",
        "cwd": str(repository),
        "tool_input": {"file_path": str(file)},
    }
    done = run("hook", "run", "lint", input=json.dumps(payload))
    assert done.exit_code == 0, done.output
    return json.loads(done.stdout) if done.stdout else {}


def test_the_lint_hook_tells_claude_what_is_wrong_with_the_document(repository):
    spec = repository / "intent" / "claims" / "spec.md"
    spec.write_text("---\nkind: plan\n---\n")
    context = lint_hook(repository, spec)["hookSpecificOutput"]["additionalContext"]
    assert "intent/claims/spec.md: [kind]" in context


def test_the_lint_hook_is_silent_for_a_clean_document_and_for_other_files(repository):
    assert lint_hook(repository, repository / "intent" / "claims" / "intent.md") == {}
    broken(repository)
    assert lint_hook(repository, repository / "app.py") == {}


def test_the_lint_hook_stays_out_of_a_folder_that_is_not_a_repository(
    repository, tmp_path_factory
):
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "intent" / "a" / "spec.md"
    assert lint_hook(repository, elsewhere) == {}


def test_a_hook_that_matches_nothing_is_status_3():
    done = run("hook", "run", "nothing", input="{}")
    assert (done.exit_code, "The hooks are: guard, lint" in done.stderr) == (3, True)
    done = run("hook", "new", "nothing")
    assert (done.exit_code, "The git hooks are: pre-push" in done.stderr) == (3, True)


def test_hook_new_installs_the_git_hook_and_prints_where(repository):
    done = run("hook", "new", "pre-push", "--root", repository)
    path = repository / ".git" / "hooks" / "pre-push"
    assert (done.exit_code, done.stdout.strip()) == (0, str(path))
    assert "exec asdlc branch check" in path.read_text()
    assert run("hook", "new", "pre-push", "--root", repository).exit_code == 0


def test_hook_new_leaves_a_hook_it_did_not_write_unless_forced(repository):
    path = repository / ".git" / "hooks" / "pre-push"
    path.write_text("#!/bin/sh\nnpm test\n")
    done = run("hook", "new", "pre-push", "--root", repository)
    assert (done.exit_code, "--force" in done.stderr) == (1, True)
    assert path.read_text() == "#!/bin/sh\nnpm test\n"
    assert (
        run("hook", "new", "pre-push", "--force", "--root", repository).exit_code == 0
    )
    assert "exec asdlc branch check" in path.read_text()


def test_the_installed_git_hook_stops_a_push_the_guard_denies(
    repository, tmp_path_factory
):
    remote = tmp_path_factory.mktemp("remote")
    git(remote, "init", "-q", "--bare")
    git(repository, "remote", "add", "origin", str(remote))
    git(repository, "push", "-q", "origin", "main")
    spec_and_code(repository)
    run("hook", "new", "pre-push", "--root", repository)
    import shutil
    import subprocess

    if shutil.which("asdlc") is None:
        pytest.skip("asdlc is not on PATH, so the hook would let the push through")
    pushed = subprocess.run(
        ["git", "-C", str(repository), "push", "origin", "spec/claims"],
        capture_output=True,
        text=True,
    )
    assert pushed.returncode != 0
    assert "app.py" in pushed.stdout + pushed.stderr


def known_to_git(repository):
    """Tell git who commits here, as a person's own repository does."""
    git(repository, "config", "user.name", "Dana")
    git(repository, "config", "user.email", "dana@example.com")
    return repository


def test_intent_new_records_the_start_before_it_writes_the_file(repository):
    done = run("intent", "new", "slow-claims", "--root", known_to_git(repository))
    assert (done.exit_code, done.stdout.strip()) == (
        0,
        "intent/slow-claims/intent.md",
    )
    log = git(repository, "log", "--format=%s", "main..HEAD").strip().split("\n")
    assert log == ["Start intent slow-claims"]
    assert git(repository, "diff", "--name-only", "main", "HEAD").strip() == ""
    assert "author: Dana" in (repository / done.stdout.strip()).read_text()

    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "Intent: slow claims")
    guard = run("branch", "check", "--root", repository)
    assert (guard.exit_code, guard.stdout) == (0, "")


def test_intent_new_records_one_start_however_often_it_is_asked(repository):
    run("intent", "new", "slow-claims", "--root", known_to_git(repository))
    again = run("intent", "new", "slow-claims", "--root", repository)
    assert again.exit_code == 1
    assert "already exists" in again.stderr
    assert git(repository, "rev-list", "--count", "main..HEAD").strip() == "1"


def test_intent_new_writes_nothing_when_git_cannot_tell_who_commits(
    repository, monkeypatch
):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(repository, "config", "user.useConfigOnly", "true")
    done = run("intent", "new", "slow-claims", "--author", "Dana", "--root", repository)
    assert done.exit_code == 1
    assert "user.name and user.email" in done.stderr
    assert not (repository / "intent" / "slow-claims" / "intent.md").exists()


EXPORT = {"intent/claims/tasks/03-export/task.md": task_text(2, "R2", 3, "the export")}


def task_ids(root) -> list[str]:
    done = run("task", "list", "--root", root)
    assert done.exit_code == 0, done.output
    return [line.split("\t")[0] for line in done.stdout.splitlines()]


def test_what_the_remote_fixture_holds_lints_clean(remote):
    done = run("document", "check", "--root", remote)
    assert (done.exit_code, done.stdout) == (0, "")
    assert task_ids(remote) == ["claims/01-endpoint", "claims/02-panel"]


def test_a_task_on_a_branch_that_is_not_merged_is_not_listed(remote):
    git(remote, "switch", "-q", "-c", "tasks/claims")
    commit_files(remote, EXPORT, "Tasks: claims")
    git(remote, "push", "-q", "origin", "tasks/claims")
    assert task_ids(remote) == ["claims/01-endpoint", "claims/02-panel"]
    assert run("task", "show", "claims/03-export", "--root", remote).exit_code == 3


def test_the_tasks_are_the_remotes_when_the_local_main_is_behind(remote):
    other = second_clone(remote)
    commit_files(other, EXPORT, "Tasks: claims")
    git(other, "push", "-q", "origin", "main")

    assert task_ids(remote)[-1] == "claims/03-export"
    shown = run("task", "show", "claims/03-export", "--root", remote)
    assert (shown.exit_code, "the export" in shown.stdout) == (0, True)
    assert git(remote, "rev-list", "--count", "main..origin/main").strip() == "1"


def test_a_branch_another_clone_pushed_reads_as_claimed_with_no_fetch_by_hand(remote):
    git(second_clone(remote), "push", "-q", "origin", "main:task/claims/01-endpoint")
    rows = json.loads(run("task", "list", "--json", "--root", remote).stdout)
    assert {row["id"]: row["state"] for row in rows} == {
        "claims/01-endpoint": "claimed",
        "claims/02-panel": "ready",
    }
    shown = run("task", "show", "claims/01-endpoint", "--root", remote)
    assert "state\tclaimed" in shown.stdout


def test_a_fetch_that_fails_warns_and_the_tasks_are_as_last_fetched(remote):
    git(remote, "remote", "set-url", "origin", str(remote.parent / "gone.git"))
    listed = run("task", "list", "--root", remote)
    assert listed.exit_code == 0
    assert "Warning: could not fetch from the remote" in listed.stderr
    assert listed.stdout.count("\n") == 2
    shown = run("task", "show", "claims/02-panel", "--root", remote)
    assert shown.exit_code == 0
    assert "Warning: could not fetch from the remote" in shown.stderr


def test_a_root_below_the_top_lists_the_tasks_that_folder_has_on_main(remote):
    below = {
        f"examples/demo/{path}": text
        for path, text in (ACCEPTED | EXPORT).items()
        if path.startswith("intent/")
    }
    commit_files(remote, below, "an example")
    git(remote, "push", "-q", "origin", "main")
    late = remote / "examples/demo/intent/claims/tasks/04-late/task.md"
    late.parent.mkdir()
    late.write_text(task_text(1, "R1", 1, "not committed"))

    assert task_ids(remote / "examples" / "demo") == [
        "claims/01-endpoint",
        "claims/02-panel",
        "claims/03-export",
    ]
    assert task_ids(remote) == ["claims/01-endpoint", "claims/02-panel"]


def test_with_no_remote_the_tasks_are_those_on_the_local_main(repository):
    commit_files(repository, ACCEPTED, "claims, accepted")
    git(repository, "switch", "-q", "-c", "tasks/claims")
    commit_files(repository, EXPORT, "Tasks: claims")
    done = run("task", "list", "--root", repository)
    assert (done.exit_code, done.stderr) == (0, "")
    assert task_ids(repository) == ["claims/01-endpoint", "claims/02-panel"]


def test_in_a_folder_that_is_no_repository_the_tasks_are_read_from_its_files(
    tmp_path,
):
    for relative, text in (ACCEPTED | EXPORT).items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text)
    assert task_ids(tmp_path)[-1] == "claims/03-export"


def test_only_the_task_commands_fetch(remote):
    git(second_clone(remote), "push", "-q", "origin", "main:task/claims/01-endpoint")
    for command in (
        ("intent", "list"),
        ("intent", "show", "claims"),
        ("requirement", "list"),
        ("document", "check"),
    ):
        assert run(*command, "--root", remote).exit_code == 0, command
        known = git(remote, "branch", "-r", "--list", "origin/task/*").strip()
        assert known == "", command
    run("task", "list", "--root", remote)
    assert git(remote, "branch", "-r", "--list", "origin/task/*").strip() != ""


ENDPOINT = "task/claims/01-endpoint"
LINK = "https://example.invalid/pull/7"


def shown_json(root, *command: str):
    done = run(*command, "--json", "--root", root)
    assert done.exit_code == 0, done.output
    return json.loads(done.stdout)


def states_shown(root, id: str = "claims/01-endpoint") -> dict[str, str]:
    """Give a task's state in each of the four places a state is shown."""
    intent = run("intent", "show", "claims", "--root", root).stdout.splitlines()
    row = f"task\t{id}\t"
    return {
        "intent show": next(
            line.removeprefix(row) for line in intent if line.startswith(row)
        ),
        "intent list": next(
            task["state"]
            for task in shown_json(root, "intent", "list")[0]["tasks"]
            if task["id"] == id
        ),
        "task list": next(
            task["state"]
            for task in shown_json(root, "task", "list")
            if task["id"] == id
        ),
        "task show": shown_json(root, "task", "show", id)["state"],
    }


def everywhere(state: str) -> dict[str, str]:
    return dict.fromkeys(
        ("intent show", "intent list", "task list", "task show"), state
    )


ASKED = "pr list --state open --limit 500 --json headRefName,isDraft,number,url"


# What a pull request makes of a task is decided in `domain/tasks.py`, and
# `tests/domain/test_tasks.py` checks each case. These two check the wiring:
# that every command that shows a state asks `gh`, and shows what was decided.


def test_each_place_a_state_is_shown_reads_the_open_pull_requests(remote, gh):
    # The task has no branch anywhere, so only its pull request can claim it.
    write_pulls(gh, pull_row(ENDPOINT, 7, draft=True))
    assert states_shown(remote) == everywhere("claimed")
    assert calls(gh) == [ASKED.split(" ")] * 4
    assert git(remote, "branch", "--all", "--list", "*task/*").strip() == ""

    write_pulls(gh, pull_row(ENDPOINT, 7))
    assert states_shown(remote) == everywhere("in review")

    listed = shown_json(remote, "task", "list")
    assert [(row["id"], row["state"], row["pull_request"]) for row in listed] == [
        ("claims/01-endpoint", "in review", LINK),
        ("claims/02-panel", "ready", None),
    ]
    assert shown_json(remote, "task", "show", "claims/01-endpoint")["pull_request"] == (
        LINK
    )
    shown = run("task", "show", "claims/01-endpoint", "--root", remote)
    assert f"pull-request\t{LINK}" in shown.stdout.splitlines()


def test_with_a_gh_that_fails_the_tasks_are_listed_and_none_is_in_review(remote, gh):
    git(remote, "push", "-q", "origin", f"main:{ENDPOINT}")
    write_pulls(gh, pull_row(ENDPOINT, 7))
    gh.fail.write_text("list\n")

    listed = run("task", "list", "--json", "--root", remote, "-v")

    assert listed.exit_code == 0
    rows = json.loads(listed.stdout)
    assert [(row["state"], row["pull_request"]) for row in rows] == [
        ("claimed", None),
        ("ready", None),
    ]
    assert "listed no pull requests, so no task reads as in review" in listed.stderr
