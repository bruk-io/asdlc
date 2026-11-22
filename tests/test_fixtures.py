"""The repositories the other tests are handed are copies of ones git made once.

A copy that still pointed at what it was copied from would let one test's push
reach the next test. These check that a copy is whole and is its own.
"""

from tests.conftest import commit_files, git, second_clone


def test_a_copied_remote_points_at_its_own_bare_repository(remote, remote_template):
    origin = remote.parent / "origin.git"
    assert git(remote, "remote", "get-url", "origin").strip() == str(origin)
    assert git(remote, "status", "--porcelain") == ""
    assert git(remote, "rev-parse", "main") == git(origin, "rev-parse", "main")

    git(remote, "push", "-q", "origin", "main:refs/heads/probe")
    assert git(origin, "branch", "--list", "probe").strip() == "probe"
    assert git(remote_template / "origin.git", "branch", "--list", "probe") == ""


def test_no_file_git_reads_in_a_copied_remote_names_the_template(
    remote, remote_template
):
    # The clone's reflog says where it was cloned from. Git reads no path out of it.
    logs = remote / ".git" / "logs"
    named = [
        path.relative_to(remote.parent)
        for path in remote.parent.rglob("*")
        if path.is_file()
        and logs not in path.parents
        and str(remote_template).encode() in path.read_bytes()
    ]
    assert named == []


def test_a_clone_finds_no_gh_until_the_stand_in_is_put_beside_it(remote):
    program = remote.parent / "gh" / "gh"
    assert git(remote, "config", "asdlc.gh").strip() == str(program)
    assert git(second_clone(remote), "config", "asdlc.gh").strip() == str(program)
    assert not program.exists()


def test_a_copied_repository_is_clean_and_changes_alone(
    repository, repository_template
):
    assert git(repository, "status", "--porcelain") == ""
    assert git(repository, "branch", "--show-current").strip() == "main"

    commit_files(repository, {"app.py": "print('one')\n"}, "code")
    assert git(repository, "rev-list", "--count", "main").strip() == "2"
    assert git(repository_template, "rev-list", "--count", "main").strip() == "1"
    assert not (repository_template / "app.py").exists()
