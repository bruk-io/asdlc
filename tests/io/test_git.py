from asdlc.io import files, git
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
