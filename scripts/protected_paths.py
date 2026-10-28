#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""A pull request that changes the plugin cannot also change the eval suite (spec R23).

The suite judges the plugin. If one change could edit both, the plugin could be graded
into passing, so eval cases arrive in pull requests of their own. The suite is `evals/`
and the evals definitions in `spec/` (`spec/*-evals.md`). Artefacts (intent, spec, plan,
incident) and the README may travel with either side.

Renames count as a deletion and an addition, so moving a file out of `evals/` still
counts as changing the suite.

Usage: protected_paths.py --base <ref> [--head <ref>]   (compares base...head; head defaults to HEAD)
"""

import re
import subprocess
import sys
from collections.abc import Iterable

_EVALS = re.compile(r"^(evals/|spec/[^/]+-evals\.md$)")
_TRAVELS_WITH_EITHER = ("intent/", "spec/", "plan/", "incident/", "README.md")


def is_suite(path: str) -> bool:
    """Whether a path is part of the eval suite: `evals/` and the evals definitions in `spec/`."""
    return bool(_EVALS.match(path))


def violation(changed: Iterable[str]) -> str | None:
    """Say why a set of changed paths breaks the rule, or None when it doesn't."""
    paths = sorted(set(changed))
    evals = [p for p in paths if _EVALS.match(p)]
    plugin = [p for p in paths if not _EVALS.match(p) and not p.startswith(_TRAVELS_WITH_EITHER)]
    if evals and plugin:
        return (
            "this change edits the eval suite and the plugin together. The suite judges the "
            "plugin, so eval cases go in a pull request of their own.\n"
            f"  eval files: {', '.join(evals)}\n"
            f"  plugin files: {', '.join(plugin)}"
        )
    return None


def _changed(base: str, head: str) -> list[str]:
    done = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        capture_output=True, text=True, check=True,
    )
    return [line for line in done.stdout.splitlines() if line]


def _arguments(argv: list[str]) -> dict[str, str] | None:
    pairs = dict(zip(argv[1::2], argv[2::2]))
    if len(argv) % 2 == 0 or "--base" not in pairs or set(pairs) - {"--base", "--head"}:
        return None
    return pairs


def main(argv: list[str]) -> int:
    arguments = _arguments(argv)
    if arguments is None:
        print(__doc__, file=sys.stderr)
        return 2
    problem = violation(_changed(arguments["--base"], arguments.get("--head", "HEAD")))
    if problem:
        print(f"protected-paths: {problem}")
        return 1
    print("protected-paths: the eval suite and the plugin are not changed together")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
