import pytest

from asdlc.domain.shell import push_folder


@pytest.mark.parametrize(
    ("command", "folder"),
    [
        ("git push", ""),
        ("git push origin spec/claims", ""),
        ("git push -u origin HEAD", ""),
        ("FOO=bar git push", ""),
        ("just check && git push", ""),
        ("git add -A; git commit -m x; git push", ""),
        ("git -C /repo push", "/repo"),
        ("git -C '/my repo' push origin main", "/my repo"),
        ("git -c user.name=t -C /repo push", "/repo"),
        ("git --no-pager push", ""),
    ],
)
def test_where_a_command_pushes_from(command, folder):
    assert push_folder(command) == folder


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git commit -m 'git push later'",
        "echo git push",
        "git log --oneline | grep push",
        "git stash push",
        "gh pr create",
        "git -C /repo status",
        "echo 'unclosed",
        "",
    ],
)
def test_a_command_that_is_not_a_push(command):
    assert push_folder(command) is None
