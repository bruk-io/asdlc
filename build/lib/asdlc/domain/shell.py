"""Reading a shell command for the one thing asdlc cares about: is it a git push?"""

import re
import shlex

_SEPARATORS = re.compile(r"&&|\|\||[;|\n]")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_GIT_OPTIONS_WITH_A_VALUE = ("-c", "--git-dir", "--work-tree", "--namespace")


def push_folder(command: str) -> str | None:
    """Say where a command runs `git push`: the `-C` folder, or "" for where it is run.

    Return None when no part of the command is a git push. A part that cannot be
    read as words is passed over, so this never mistakes one for a push.
    """
    for part in _SEPARATORS.split(command):
        try:
            words = shlex.split(part)
        except ValueError:
            continue
        while words and _ASSIGNMENT.match(words[0]):
            words = words[1:]
        if not words or words[0] != "git":
            continue
        folder = ""
        at = 1
        while at < len(words) and words[at].startswith("-"):
            if words[at] == "-C" and at + 1 < len(words):
                folder = words[at + 1]
                at += 2
            elif words[at] in _GIT_OPTIONS_WITH_A_VALUE:
                at += 2
            else:
                at += 1
        if at < len(words) and words[at] == "push":
            return folder
    return None
