#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""asdlc launcher: run `asdlc` or `asdlc-plugin` from the installed asdlc plugin.

`asdlc install-command` copies this file onto a person's PATH as `asdlc` and `asdlc-plugin`.
It holds no asdlc logic. Each time it runs it finds the plugin and runs the script of the
same name there, so the command a person and their agents type is always the release whose
skills, agents and hooks are in use, whatever is checked out in a clone of the repository.

Where it looks, in order:

1. An asdlc plugin's `bin` folder on PATH. Claude Code adds it for every plugin a session
   loaded, so inside a session this is the release that session is running, even when a
   newer one has been installed since.
2. Claude Code's install records (`installed_plugins.json`): the install made for the folder
   you are in, then the install for every project, then the newest.

A working copy is never found this way. Run it by its path, `<clone>/scripts/asdlc`.

The plugins folder is $CLAUDE_CODE_PLUGIN_CACHE_DIR, else $CLAUDE_CONFIG_DIR/plugins, else
~/.claude/plugins.
"""

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

COMMANDS = ("asdlc", "asdlc-plugin")
PLUGIN = "asdlc"
MANIFEST = Path(".claude-plugin") / "plugin.json"
RECORDS = "installed_plugins.json"


@dataclass(frozen=True)
class Install:
    """One install of the asdlc plugin, as Claude Code recorded it."""

    root: Path
    version: str
    commit: str
    project: Path | None  # the folder it was installed for; None when it is for every project
    updated: str


@dataclass(frozen=True)
class Release:
    """The plugin folder to run, and how it was found."""

    root: Path
    source: str


def installs(text: str) -> tuple[Install, ...]:
    """The asdlc plugin's installs in `installed_plugins.json`'s text; none when it is not that file."""
    try:
        plugins = json.loads(text).get("plugins")
    except (ValueError, AttributeError):
        return ()
    if not isinstance(plugins, dict):
        return ()
    found = []
    for key, rows in plugins.items():
        if not str(key).startswith(f"{PLUGIN}@") or not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and isinstance(path := row.get("installPath"), str) and path:
                project = row.get("projectPath")
                found.append(Install(Path(path), str(row.get("version", "")), str(row.get("gitCommitSha", "")),
                                     Path(project) if isinstance(project, str) and project else None, str(row.get("lastUpdated", ""))))
    return tuple(found)


def bin_parents(entries: Sequence[str]) -> tuple[Path, ...]:
    """The folders whose `bin` is on PATH, in PATH's order: where a session's plugins are, among others."""
    parents = [Path(entry).parent for entry in entries if entry and Path(entry).is_absolute() and Path(entry).name == "bin"]
    return tuple(dict.fromkeys(parents))


def choose(session: Sequence[Path], installed: Sequence[Install], cwd: Path) -> Release | None:
    """The plugin folder to run: the one this session loaded, else the best install for `cwd`; None when there is none."""
    if session:
        return Release(session[0], "the plugin this session loaded")
    here = [i for i in installed if i.project is not None and (cwd == i.project or i.project in cwd.parents)]
    if here:
        nearest = max(here, key=lambda i: (len(i.project.parts), i.updated))
        return Release(nearest.root, f"the install for {nearest.project}")
    everywhere = [i for i in installed if i.project is None]
    if everywhere:
        return Release(max(everywhere, key=lambda i: i.updated).root, "the install for every project")
    if installed:
        newest = max(installed, key=lambda i: i.updated)
        return Release(newest.root, f"the newest install, made for {newest.project}")
    return None


def plugins_folder(environ: Mapping[str, str], home: Path) -> Path:
    if folder := environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR", "").strip():
        return Path(folder).expanduser()
    if config := environ.get("CLAUDE_CONFIG_DIR", "").strip():
        return Path(config).expanduser() / "plugins"
    return home / ".claude" / "plugins"


def _is_asdlc(root: Path) -> bool:
    """Whether a folder is the asdlc plugin with its scripts in it."""
    try:
        name = json.loads((root / MANIFEST).read_text()).get("name")
    except (OSError, ValueError, AttributeError):
        return False
    return name == PLUGIN and all((root / "scripts" / command).is_file() for command in COMMANDS)


def read_installs(records: Path) -> tuple[Install, ...]:
    """The asdlc installs recorded on this machine whose folders are still there."""
    try:
        text = records.read_text()
    except OSError:
        return ()
    return tuple(i for i in installs(text) if _is_asdlc(i.root))


def locate(environ: Mapping[str, str], cwd: Path, home: Path) -> Release | None:
    session = [root for root in bin_parents(environ.get("PATH", "").split(os.pathsep)) if _is_asdlc(root)]
    return choose(session, read_installs(plugins_folder(environ, home) / RECORDS), cwd)


def main(program: str, arguments: Sequence[str]) -> int:
    name = Path(program).name
    if name not in COMMANDS:
        print(f"asdlc launcher: this file is named {name}, and it only runs as asdlc or asdlc-plugin. Install it with asdlc install-command.", file=sys.stderr)
        return 1
    release = locate(os.environ, Path.cwd(), Path.home())
    if release is None:
        records = plugins_folder(os.environ, Path.home()) / RECORDS
        print(f"{name}: no installed asdlc plugin was found, so there is nothing to run. Looked for the plugin's bin folder on PATH and in "
              f"{records}. Install the plugin in Claude Code (/plugin install asdlc@asdlc), or run a working copy by its path "
              f"(<clone>/scripts/{name}).", file=sys.stderr)
        return 1
    target = release.root / "scripts" / name
    try:
        os.execvp("uv", ["uv", "run", "--quiet", "--script", str(target), *arguments])
    except OSError as error:
        print(f"{name}: could not run {target} through uv: {error}. Install uv: https://docs.astral.sh/uv/", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[0], sys.argv[1:]))
