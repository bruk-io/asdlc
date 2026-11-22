import time

from asdlc.io import files, git
from tests.conftest import ACCEPTED, commit_files, second_clone
from tests.conftest import git as run_git


def test_what_git_knows_about_a_branch(repository):
    run_git(repository, "switch", "-q", "-c", "spec/claims")
    (repository / "intent" / "claims" / "spec.md").write_text("---\nkind: spec\n---\n")
    (repository / "app.py").write_text("print('too early')\n")
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "-q", "-m", "spec and code")

    assert git.repository(repository / "intent") == repository
    assert git.base(repository) == "main"
    assert git.current_branch(repository) == "spec/claims"
    assert git.documents_on(repository, "main") == {"intent/claims/intent.md"}
    assert git.changed_since(repository, "main") == ("app.py", "intent/claims/spec.md")


def test_a_folder_outside_any_repository(tmp_path):
    assert git.repository(tmp_path) is None
    assert git.base(tmp_path) is None


def test_document_texts_are_paths_from_the_root_with_their_text(repository):
    assert files.document_texts(repository) == (
        ("intent/claims/intent.md", "---\nkind: intent\nauthor: a\n---\n"),
    )


def test_where_a_path_sits(repository, tmp_path):
    new = repository / "src" / "deep" / "app.py"
    assert files.nearest_folder(new) == repository
    assert files.inside(new, repository) == "src/deep/app.py"
    assert files.inside(tmp_path.parent / "elsewhere.md", repository) is None


def test_a_branch_is_made_from_main_and_switched_to(repository):
    assert git.create_branch(repository, "spec/claims", "main") is True
    assert git.current_branch(repository) == "spec/claims"
    assert git.has_branch(repository, "spec/claims") is True
    assert git.create_branch(repository, "spec/claims", "main") is False


def test_changes_are_read_from_a_named_branch_not_only_the_current_one(repository):
    run_git(repository, "switch", "-q", "-c", "spec/claims")
    (repository / "app.py").write_text("x = 1\n")
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "-q", "-m", "code")
    run_git(repository, "switch", "-q", "main")
    assert git.changed_since(repository, "main") == ()
    assert git.changed_since(repository, "main", "spec/claims") == ("app.py",)


def test_a_program_is_written_where_git_runs_hooks_from(repository):
    hook = git.hooks_folder(repository) / "pre-push"
    assert hook.parent == repository / ".git" / "hooks"
    assert files.read_text(hook) is None
    files.write_program(hook, "#!/bin/sh\n")
    assert files.read_text(hook) == "#!/bin/sh\n"
    assert hook.stat().st_mode & 0o111


def test_branches_and_merges_are_read_from_git(repository):
    run_git(repository, "switch", "-q", "-c", "task/claims/01-a")
    (repository / "app.py").write_text("x = 1\n")
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "-q", "-m", "code")
    run_git(repository, "switch", "-q", "main")
    assert git.branches(repository) == {"main", "task/claims/01-a"}
    assert git.merge_subjects(repository, "main") == ()
    subject = "Merge pull request #4 from o/task/claims/01-a"
    run_git(repository, "merge", "-q", "--no-ff", "-m", subject, "task/claims/01-a")
    assert git.merge_subjects(repository, "main") == (subject,)


def test_switching_to_a_branch_that_exists(repository):
    git.create_branch(repository, "spec/claims", "main")
    assert git.switch(repository, "main") is True
    assert git.current_branch(repository) == "main"
    assert git.switch(repository, "nothing") is False


def test_a_new_file_is_written_once(repository):
    path = repository / "intent" / "new" / "intent.md"
    assert files.write_new(path, "first") is True
    assert files.write_new(path, "second") is False
    assert path.read_text() == "first"


def test_an_empty_commit_changes_no_file_and_leaves_what_is_staged(repository):
    run_git(repository, "config", "user.name", "t")
    run_git(repository, "config", "user.email", "t@example.com")
    run_git(repository, "switch", "-q", "-c", "intent/new")
    (repository / "staged.py").write_text("x = 1\n")
    run_git(repository, "add", "staged.py")
    assert git.ahead(repository, "main") == 0

    assert git.commit_empty(repository, "Start intent new") is True

    assert git.ahead(repository, "main") == 1
    assert run_git(repository, "log", "-1", "--format=%s").strip() == "Start intent new"
    assert git.changed_since(repository, "main") == ()
    assert run_git(repository, "diff", "--cached", "--name-only").strip() == "staged.py"


def test_an_empty_commit_is_refused_when_git_cannot_tell_who_commits(
    repository, monkeypatch
):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    run_git(repository, "config", "user.useConfigOnly", "true")
    assert git.commit_empty(repository, "Start intent new") is False
    assert git.ahead(repository, "main") == 0


def test_a_setting_is_read_from_gits_configuration_and_is_empty_when_not_set(
    repository,
):
    assert git.setting(repository, "asdlc.gh") == ""
    run_git(repository, "config", "asdlc.gh", "/somewhere/with a space/gh")
    assert git.setting(repository, "asdlc.gh") == "/somewhere/with a space/gh"


def test_a_repository_knows_whether_it_has_a_remote(repository, remote):
    assert git.has_remote(repository) is False
    assert git.has_remote(remote) is True


def test_a_fetch_brings_in_what_another_clone_pushed_and_prunes_what_it_deleted(
    remote,
):
    other = second_clone(remote)
    run_git(other, "push", "-q", "origin", "main:task/claims/01-endpoint")
    assert git.remote_branches(remote) == {"main"}

    assert git.fetch(remote) is True
    assert git.remote_branches(remote) == {"main", "task/claims/01-endpoint"}

    run_git(other, "push", "-q", "origin", ":task/claims/01-endpoint")
    assert git.fetch(remote) is True
    assert git.remote_branches(remote) == {"main"}


def test_a_fetch_that_cannot_reach_the_remote_says_so(remote):
    run_git(remote, "remote", "set-url", "origin", str(remote.parent / "gone.git"))
    assert git.fetch(remote) is False


def test_a_fetch_gives_up_at_its_limit(remote, monkeypatch):
    run_git(remote, "remote", "set-url", "origin", "ssh://nowhere.invalid/claims.git")
    monkeypatch.setenv("GIT_SSH_COMMAND", "sh -c 'sleep 5'")
    began = time.monotonic()
    assert git.fetch(remote, limit=0.5) is False
    assert time.monotonic() - began < 4


def test_documents_are_read_at_a_ref_and_not_from_the_working_tree(remote):
    (remote / "intent" / "claims" / "spec.md").write_text("changed, not committed\n")
    read = git.document_texts_at(remote, "origin/main")
    documents = sorted(path for path in ACCEPTED if path.endswith(".md"))
    assert [path for path, _ in read] == documents
    assert dict(read)["intent/claims/spec.md"] == ACCEPTED["intent/claims/spec.md"]


def test_documents_below_a_prefix_come_with_paths_from_that_prefix(remote):
    intent = "---\nkind: intent\nauthor: a\n---\n"
    commit_files(remote, {"examples/demo/intent/x/intent.md": intent}, "an example")
    assert git.document_texts_at(remote, "main", "examples/demo/") == (
        ("intent/x/intent.md", intent),
    )
    assert git.document_texts_at(remote, "origin/main", "examples/demo/") == ()
    assert git.document_texts_at(remote, "no-such-ref") == ()


def test_a_file_is_read_at_a_ref_and_is_none_when_the_ref_has_none(remote):
    (remote / ".asdlc" / "checks").write_text("true\n")
    assert git.file_at(remote, "origin/main", ".asdlc/checks") == "echo checked\n"
    assert git.file_at(remote, "origin/main", ".asdlc/nothing") is None
    assert git.file_at(remote, "origin/no-such-branch", ".asdlc/checks") is None


def test_a_clean_checkout_has_nothing_uncommitted(remote):
    assert git.uncommitted(remote) == ()


def test_what_is_uncommitted_is_changed_staged_and_untracked_and_not_ignored(remote):
    (remote / ".git" / "info" / "exclude").write_text("scratch/\n")
    (remote / "scratch").mkdir()
    (remote / "scratch" / "notes.txt").write_text("ignored\n")
    (remote / "intent" / "claims" / "spec.md").write_text("changed\n")
    (remote / "a new file.py").write_text("x = 1\n")
    (remote / "staged.py").write_text("y = 2\n")
    run_git(remote, "add", "staged.py")
    run_git(remote, "mv", "intent/claims/plan.md", "intent/claims/moved.md")
    run_git(remote, "rm", "-q", ".asdlc/checks")

    assert sorted(git.uncommitted(remote)) == [
        ".asdlc/checks",
        "a new file.py",
        "intent/claims/moved.md",
        "intent/claims/spec.md",
        "staged.py",
    ]


def test_a_position_is_the_branch_or_the_commit_and_the_checkout_goes_back_to_it(
    remote,
):
    assert git.position(remote) == "main"
    assert git.switch_new(remote, "task/claims/01-endpoint", "origin/main") is True
    assert git.switch_back(remote, "main") is True
    assert git.current_branch(remote) == "main"

    commit = run_git(remote, "rev-parse", "HEAD").strip()
    run_git(remote, "switch", "-q", "--detach", "main")
    assert git.position(remote) == commit
    run_git(remote, "switch", "-q", "task/claims/01-endpoint")
    assert git.switch_back(remote, commit) is True
    assert (git.current_branch(remote), git.position(remote)) == ("", commit)
    assert git.switch_back(remote, "no-such-branch") is False


def test_a_new_branch_takes_no_upstream_and_one_from_create_branch_takes_main(remote):
    assert git.switch_new(remote, "task/claims/01-endpoint", "origin/main") is True
    assert git.current_branch(remote) == "task/claims/01-endpoint"
    assert git.setting(remote, "branch.task/claims/01-endpoint.merge") == ""
    assert git.switch_new(remote, "task/claims/01-endpoint", "origin/main") is False

    assert git.create_branch(remote, "spec/other", "origin/main") is True
    assert git.setting(remote, "branch.spec/other.merge") == "refs/heads/main"


def test_a_local_branch_is_deleted_merged_or_not(remote):
    git.switch_new(remote, "task/claims/01-endpoint", "origin/main")
    commit_files(remote, {"api/status.py": "x = 1\n"}, "not merged anywhere")
    assert git.delete_branch(remote, "task/claims/01-endpoint") is False
    git.switch(remote, "main")
    assert git.delete_branch(remote, "task/claims/01-endpoint") is True
    assert git.has_branch(remote, "refs/heads/task/claims/01-endpoint") is False
    assert git.delete_branch(remote, "task/claims/01-endpoint") is False


def test_each_worktrees_branch_is_listed_with_its_folder(remote):
    tree = remote.parent / "tree"
    loose = remote.parent / "loose"
    run_git(remote, "worktree", "add", "-q", "-b", "worktree-one", str(tree), "main")
    run_git(remote, "worktree", "add", "-q", "--detach", str(loose), "main")
    assert git.checked_out(remote) == {"main": remote, "worktree-one": tree}
    assert git.checked_out(tree) == git.checked_out(remote)
    assert git.held_elsewhere(remote) == {"worktree-one": str(tree)}
    assert git.held_elsewhere(tree) == {"main": str(remote)}


def test_a_claiming_push_answers_with_a_star_only_when_it_made_the_branch(remote):
    branch = "task/claims/01-endpoint"
    other = second_clone(remote)
    for clone in (remote, other):
        git.switch_new(clone, branch, "origin/main")
        commit_files(clone, {"who.txt": f"{clone.name}\n"}, "Start")

    # The line a push prints for the branch is flag, refs, summary, with tabs
    # between. The flag is what says whether the push made the branch.
    refs = f"refs/heads/{branch}:refs/heads/{branch}"

    first = git.push_claim(remote, branch)
    assert first.ok is True
    assert first.out.splitlines()[1] == f"*\t{refs}\t[new branch]"
    assert git.setting(remote, f"branch.{branch}.merge") == f"refs/heads/{branch}"

    again = git.push_claim(remote, branch)
    assert again.ok is True
    assert again.out.splitlines()[1] == f"=\t{refs}\t[up to date]"

    late = git.push_claim(other, branch)
    assert late.ok is False
    assert late.out.splitlines()[1].startswith(f"!\t{refs}\t[rejected]")
    kept = run_git(remote.parent / "origin.git", "rev-parse", branch)
    assert kept == run_git(remote, "rev-parse", "HEAD")


def test_a_claiming_push_leaves_a_branch_the_remote_already_has_even_one_behind(
    remote,
):
    branch = "task/claims/01-endpoint"
    origin = remote.parent / "origin.git"
    run_git(second_clone(remote), "push", "-q", "origin", f"main:{branch}")
    there = run_git(origin, "rev-parse", branch)
    git.switch_new(remote, branch, "origin/main")
    git.commit_empty(remote, "Start task claims/01-endpoint")

    late = git.push_claim(remote, branch)

    assert late.ok is False
    assert late.out.splitlines()[1].startswith("!\t")
    assert run_git(origin, "rev-parse", branch) == there


def test_a_branch_is_deleted_from_the_remote_only_while_it_is_at_the_commit_given(
    remote,
):
    branch = "task/claims/01-endpoint"
    origin = remote.parent / "origin.git"
    git.switch_new(remote, branch, "origin/main")
    git.commit_empty(remote, "Start task claims/01-endpoint")
    mine = git.head(remote)
    assert mine == run_git(remote, "rev-parse", "HEAD").strip()
    git.push_claim(remote, branch)

    other = second_clone(remote)
    run_git(other, "switch", "-q", branch)
    commit_files(other, {"api/status.py": "x = 1\n"}, "someone else's work")
    run_git(other, "push", "-q", "origin", branch)
    theirs = run_git(other, "rev-parse", "HEAD").strip()

    assert git.delete_remote(remote, branch, mine) is False
    assert run_git(origin, "rev-parse", branch).strip() == theirs

    assert git.delete_remote(remote, branch, theirs) is True
    assert run_git(origin, "branch", "--list", branch) == ""
    assert git.delete_remote(remote, branch, theirs) is False


def test_a_push_to_a_remote_that_is_gone_says_so_and_answers_nothing(remote):
    git.switch_new(remote, "task/claims/01-endpoint", "origin/main")
    run_git(remote, "remote", "set-url", "origin", str(remote.parent / "gone.git"))
    pushed = git.push_claim(remote, "task/claims/01-endpoint")
    assert (pushed.ok, pushed.out) == (False, "")
    assert "gone.git" in pushed.err


def test_the_commits_of_a_range_come_oldest_first_with_their_files_and_no_merges(
    remote,
):
    git.switch_new(remote, "task/claims/01-endpoint", "origin/main")
    assert git.commits(remote, "origin/main..HEAD") == ()
    git.commit_empty(remote, "Start task claims/01-endpoint")
    commit_files(
        remote, {"api/status.py": "x = 1\n", "api/caf\u00e9 one.py": ""}, "the endpoint"
    )
    run_git(remote, "switch", "-q", "main")
    commit_files(remote, {"README.md": "claims\n"}, "on main")
    run_git(remote, "switch", "-q", "task/claims/01-endpoint")
    run_git(remote, "merge", "-q", "--no-ff", "-m", "Merge main", "main")

    found = git.commits(remote, "origin/main..HEAD")
    assert {subject: changed for _, subject, changed in found} == {
        "Start task claims/01-endpoint": (),
        "the endpoint": ("api/caf\u00e9 one.py", "api/status.py"),
        "on main": ("README.md",),
    }
    assert len(found) == 3
    subjects = [subject for _, subject, _ in found]
    assert subjects.index("Start task claims/01-endpoint") < subjects.index(
        "the endpoint"
    )
    for id, subject, _ in found:
        assert run_git(remote, "log", "-1", "--format=%s", id).strip() == subject
    assert git.commits(remote, "no-such-ref..HEAD") == ()


def test_a_merge_that_conflicts_is_left_and_its_files_are_listed(remote):
    git.switch_new(remote, "task/claims/01-endpoint", "origin/main")
    commit_files(remote, {"api/status.py": "status = 'here'\n"}, "here")
    run_git(remote, "switch", "-q", "main")
    commit_files(remote, {"api/status.py": "status = 'there'\n"}, "there")
    commit_files(remote, {"README.md": "claims\n"}, "no clash")
    run_git(remote, "switch", "-q", "task/claims/01-endpoint")
    assert (git.merging(remote), git.conflicts(remote)) == (False, ())

    assert git.merge(remote, "main~1") is False
    assert (git.merging(remote), git.conflicts(remote)) == (True, ("api/status.py",))

    (remote / "api" / "status.py").write_text("status = 'both'\n")
    run_git(remote, "add", "api/status.py")
    assert (git.merging(remote), git.conflicts(remote)) == (True, ())
    run_git(remote, "commit", "-q", "--no-edit")
    assert git.merging(remote) is False

    assert git.merge(remote, "main") is True
    assert (remote / "README.md").is_file()
    assert run_git(remote, "status", "--porcelain") == ""
