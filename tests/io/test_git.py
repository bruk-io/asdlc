import pytest

from asdlc.domain.documents import Kind, parse
from asdlc.io import files, git, github
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


@pytest.mark.parametrize("kind", list(Kind))
def test_every_kind_has_a_template_that_ships_with_the_package(kind):
    text = files.template(kind)
    assert text.startswith(f"---\nkind: {kind}\n")


def test_a_template_is_a_document_once_its_frontmatter_is_filled(repository):
    document, _ = parse("intent/claims/intent.md", files.template(Kind.INTENT))
    assert document.kind is Kind.INTENT


def test_a_new_file_is_written_once(repository):
    path = repository / "intent" / "new" / "intent.md"
    assert files.write_new(path, "first") is True
    assert files.write_new(path, "second") is False
    assert path.read_text() == "first"


def fake_gh(folder, monkeypatch, script: str) -> None:
    files.write_program(folder / "gh", f"#!/bin/sh\n{script}\n")
    monkeypatch.setenv("PATH", f"{folder}:/usr/bin:/bin")


def test_open_pull_requests_are_read_through_gh(
    repository, tmp_path_factory, monkeypatch
):
    rows = '[{"headRefName": "task/claims/01-a"}, {"headRefName": "spec/x"}]'
    fake_gh(tmp_path_factory.mktemp("bin"), monkeypatch, f"echo '{rows}'")
    assert github.open_pull_branches(repository) == {"task/claims/01-a", "spec/x"}


def test_gh_failing_or_missing_is_no_answer_not_an_empty_one(
    repository, tmp_path_factory, monkeypatch
):
    folder = tmp_path_factory.mktemp("bin")
    fake_gh(folder, monkeypatch, "exit 1")
    assert github.open_pull_branches(repository) is None
    monkeypatch.setenv("PATH", str(tmp_path_factory.mktemp("empty")))
    assert github.open_pull_branches(repository) is None


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
