"""What GitHub knows and git does not: the open pull requests, and their branches.

Everything here goes through one program: the one the git config key `asdlc.gh`
names, and `gh` when the key is not set.

GitHub opens a draft pull request on a branch whose only commit is empty: tried
on 2026-11-18, with pull request #101.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from asdlc.io import git

_FIELDS = "headRefName,isDraft,number,url"


@dataclass(frozen=True)
class Pull:
    """An open pull request."""

    branch: str
    number: int
    link: str
    draft: bool


def program(root: Path) -> str:
    """Give the program that is run for GitHub in this repository."""
    return git.setting(root, "asdlc.gh") or "gh"


def _answer(root: Path, *args: str) -> str | None:
    """Run the program and give what it printed; None when it is missing or fails."""
    try:
        done = subprocess.run(
            [program(root), *args], capture_output=True, text=True, cwd=root
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def _pull(row: object) -> Pull | None:
    """Read one row of `pr list --json`; None when it names no branch."""
    if not isinstance(row, dict) or not isinstance(row.get("headRefName"), str):
        return None
    number, link = row.get("number"), row.get("url")
    return Pull(
        branch=row["headRefName"],
        number=number if isinstance(number, int) else 0,
        link=link if isinstance(link, str) else "",
        draft=row.get("isDraft") is True,
    )


def _pulls(answer: str) -> tuple[Pull, ...] | None:
    """Read what `pr list --json` printed; None when it is not that list."""
    try:
        rows = json.loads(answer or "[]")
    except ValueError:
        return None
    if not isinstance(rows, list):
        return None
    pulls = tuple(_pull(row) for row in rows)
    return None if None in pulls else tuple(pull for pull in pulls if pull)


def open_pulls(root: Path) -> tuple[Pull, ...] | None:
    """List the open pull requests: branch, number, link, and draft or not.

    A row that does not say whether it is a draft reads as not one.

    Return None when the program is not installed, not signed in, the repository
    has no GitHub remote, or what it printed is not the list asked for: the
    caller then knows the answer is missing, not empty.
    """
    answer = _answer(
        root, "pr", "list", "--state", "open", "--limit", "500", "--json", _FIELDS
    )
    return None if answer is None else _pulls(answer)
