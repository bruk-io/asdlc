"""A Claude Code hook's input: the tool call it is asked about, read from a stream."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

_WRITES = ("Edit", "Write", "NotebookEdit")


@dataclass(frozen=True)
class FileWrite:
    """A tool call that writes one file."""

    path: Path


def read_file_write(stream: TextIO) -> FileWrite | None:
    """Read a hook payload and give the file it writes; None for any other call.

    Raises:
        json.JSONDecodeError: The stream did not hold the JSON a hook is sent.
    """
    payload = json.load(stream)
    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if payload.get("tool_name") not in _WRITES or not target:
        return None
    path = Path(target)
    return FileWrite(
        path if path.is_absolute() else Path(payload.get("cwd") or ".") / path
    )


@dataclass(frozen=True)
class ShellCommand:
    """A tool call that runs a shell command, and the folder it runs in."""

    text: str
    cwd: Path


def read_shell_command(stream: TextIO) -> ShellCommand | None:
    """Read a hook payload and give the command it runs; None for any other call.

    Raises:
        json.JSONDecodeError: The stream did not hold the JSON a hook is sent.
    """
    payload = json.load(stream)
    command = (payload.get("tool_input") or {}).get("command")
    if payload.get("tool_name") != "Bash" or not command:
        return None
    return ShellCommand(command, Path(payload.get("cwd") or "."))
