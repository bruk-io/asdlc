#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""Name a release: set the plugin's version and file the changelog's Unreleased entries under it.

Claude Code keeps every install of a plugin on the version its manifest names until that
string changes. So a change reaches the machines that installed asdlc only when the version
is bumped, and a bump that is forgotten leaves them where they were without a word. This is
the one command for it. It edits `.claude-plugin/plugin.json` and `CHANGELOG.md` and nothing
else: committing, merging and tagging `v<version>` stay with the person.

Usage: release.py <version> [--date <YYYY-MM-DD>] [--root <folder>]
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

_VERSION = re.compile(r"\d+\.\d+\.\d+")
_FIELD = re.compile(r'("version"\s*:\s*")([^"]*)(")')
_UNRELEASED = "## Unreleased\n"


class ReleaseError(Exception):
    """Why the release was refused; its message says what to do."""


def _number(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def bump(manifest: str, changelog: str, version: str, day: str) -> tuple[str, str]:
    """The manifest and the changelog as they read once `version` is released on `day`.

    Raises:
        ReleaseError: the version is not three numbers or not newer than the manifest's, the manifest has no
            one version to change, or the changelog has nothing under Unreleased.
    """
    if not _VERSION.fullmatch(version):
        raise ReleaseError(f"{version} is not a version: write three numbers, such as 0.2.0")
    fields = _FIELD.findall(manifest)
    if len(fields) != 1:
        raise ReleaseError(f'the manifest has {len(fields)} "version" fields, and a release changes exactly one')
    current = fields[0][1]
    if _VERSION.fullmatch(current) and _number(version) <= _number(current):
        raise ReleaseError(f"{version} is not newer than {current}, and Claude Code only updates an install when the version changes: choose a later one")
    if changelog.count(_UNRELEASED) != 1:
        raise ReleaseError("the changelog needs exactly one '## Unreleased' heading to file the release under")
    before, after = changelog.split(_UNRELEASED)
    entries = after.split("\n## ", 1)[0]
    if not entries.strip():
        raise ReleaseError("nothing is under '## Unreleased' in the changelog, so there is nothing to release: add the entry first")
    return _FIELD.sub(rf"\g<1>{version}\g<3>", manifest), f"{before}{_UNRELEASED}\n## {version} - {day}\n{after}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="release.py", description="Set the plugin's version and file the changelog's Unreleased entries under it.")
    parser.add_argument("version")
    parser.add_argument("--date", default=date.today().isoformat(), help="the release's date (else today)")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent), help="the plugin's folder (else this script's)")
    arguments = parser.parse_args(argv)
    manifest, changelog = Path(arguments.root) / ".claude-plugin" / "plugin.json", Path(arguments.root) / "CHANGELOG.md"
    try:
        new_manifest, new_changelog = bump(manifest.read_text(), changelog.read_text(), arguments.version, arguments.date)
    except ReleaseError as error:
        print(f"release: {error}", file=sys.stderr)
        return 1
    manifest.write_text(new_manifest)
    changelog.write_text(new_changelog)
    print(f"release: {manifest} and {changelog} now say {arguments.version}. Commit them with the change, and after the merge: "
          f"git tag v{arguments.version} && git push origin v{arguments.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
