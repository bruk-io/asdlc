# /// script
# requires-python = ">=3.15"
# ///
"""A code repository's slug: `owner-repo`, lowercase, from its `origin` remote.

The slug names the repository everywhere the tasks repository refers to it: a task's
Backlog `project`, `plugins/<slug>/` in the marketplace, and `prefer` and `avoid` in a
developer's preferences. Every part of asdlc derives it here, so they always agree.

The owner and the repository are the last two parts of the remote's path, so
`git@github.com:Acme/Web-App.git`, `https://github.com/acme/web-app` and
`ssh://git@github.com:22/acme/web-app.git` are all `acme-web-app`. The host, and any group
above the owner, are dropped. Anything that isn't a lowercase letter, digit or hyphen
becomes a hyphen, so the slug is also a valid plugin name.
"""

import re
import subprocess
from pathlib import Path

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_SCP = re.compile(r"^(?:[^@/]+@)?[^/:]+:(?!//)(.*)$")


def remote_path(remote: str) -> str:
    """The path part of a git remote: after the host, or the whole local path."""
    url = remote.strip()
    if _SCHEME.match(url):
        rest = _SCHEME.sub("", url)
        return rest.partition("/")[2] if "/" in rest else ""
    if match := _SCP.match(url):
        return match.group(1)
    return url


def repo_slug(remote: str) -> str | None:
    """`owner-repo` from a remote URL, or None when it names no owner and repository."""
    parts = [part for part in remote_path(remote).replace("\\", "/").split("/") if part]
    if len(parts) < 2:
        return None
    owner, name = parts[-2], parts[-1].removesuffix(".git")
    slug = re.sub(r"[^a-z0-9]+", "-", f"{owner}-{name}".lower()).strip("-")
    return slug if owner and name and slug else None


def origin_url(repo: Path) -> str | None:
    """The `origin` remote's URL as git resolves it (insteadOf rules applied), or None."""
    done = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"], capture_output=True, text=True)
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def slug_of(repo: Path) -> str | None:
    """The slug of the repository at `repo`, or None when it has no usable `origin`."""
    url = origin_url(repo)
    return repo_slug(url) if url else None
