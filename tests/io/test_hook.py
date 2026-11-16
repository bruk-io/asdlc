import io
import json
from pathlib import Path

import pytest

from asdlc.io.hook import FileWrite, ShellCommand, read_file_write, read_shell_command


def stream(**payload: object) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


def test_a_write_names_its_file():
    call = stream(
        tool_name="Write", cwd="/repo", tool_input={"file_path": "/repo/a.py"}
    )
    assert read_file_write(call) == FileWrite(Path("/repo/a.py"))


def test_a_relative_path_is_taken_from_the_calls_folder():
    call = stream(tool_name="Edit", cwd="/repo", tool_input={"file_path": "src/a.py"})
    assert read_file_write(call) == FileWrite(Path("/repo/src/a.py"))


def test_a_notebook_edit_names_its_notebook():
    call = stream(
        tool_name="NotebookEdit", cwd="/r", tool_input={"notebook_path": "/r/n.ipynb"}
    )
    assert read_file_write(call) == FileWrite(Path("/r/n.ipynb"))


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Bash", "tool_input": {"command": "ls"}},
        {"tool_name": "Read", "tool_input": {"file_path": "/repo/a.py"}},
        {"tool_name": "Write", "tool_input": {}},
        {"tool_name": "Write"},
    ],
)
def test_any_other_call_is_not_a_file_write(payload):
    assert read_file_write(stream(**payload)) is None


def test_a_shell_call_gives_its_command_and_folder():
    call = stream(tool_name="Bash", cwd="/repo", tool_input={"command": "git push"})
    assert read_shell_command(call) == ShellCommand("git push", Path("/repo"))


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Write", "tool_input": {"file_path": "/repo/a.py"}},
        {"tool_name": "Bash", "tool_input": {}},
        {"tool_name": "Bash"},
    ],
)
def test_any_other_call_is_not_a_shell_command(payload):
    assert read_shell_command(stream(**payload)) is None
