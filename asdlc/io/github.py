"""What GitHub knows and git does not: which branches have an open pull request."""

import json
import subprocess
from pathlib import Path


def open_pull_branches(root: Path) -> frozenset[str] | None:
    """List the branches with an open pull request, through the `gh` command.

    Return None when `gh` is not installed, not signed in, or the repository has
    no GitHub remote: the caller then knows the answer is missing, not empty.
    """
    command = ["gh", "pr", "list", "--state", "open", "--limit", "500"]
    try:
        done = subprocess.run(
            [*command, "--json", "headRefName"],
            capture_output=True,
            text=True,
            cwd=root,
        )
    except FileNotFoundError:
        return None
    if done.returncode != 0:
        return None
    return frozenset(row["headRefName"] for row in json.loads(done.stdout or "[]"))
