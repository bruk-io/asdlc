#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""A pull request that changes the plugin cannot also change the eval suite (spec R23).

The suite judges the plugin. If one change could edit both, the plugin could be graded
into passing, so eval cases arrive in pull requests of their own. Artefacts (intent,
spec, plan, incident) and the README may travel with either.

Usage: protected_paths.py --base <ref>   (compares <ref>...HEAD)
"""

import subprocess
import sys
from collections.abc import Iterable

EVALS = "evals/"
TRAVELS_WITH_EITHER = ("intent/", "spec/", "plan/", "incident/", "README.md")


def violation(changed: Iterable[str]) -> str | None:
    """Say why a set of changed paths breaks the rule, or None when it doesn't."""
    paths = sorted(set(changed))
    evals = [p for p in paths if p.startswith(EVALS)]
    plugin = [p for p in paths if not p.startswith(EVALS) and not p.startswith(TRAVELS_WITH_EITHER)]
    if evals and plugin:
        return (
            "this change edits the eval suite and the plugin together. The suite judges the "
            "plugin, so eval cases go in a pull request of their own.\n"
            f"  eval files: {', '.join(evals)}\n"
            f"  plugin files: {', '.join(plugin)}"
        )
    return None


def _changed(base: str) -> list[str]:
    done = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"], capture_output=True, text=True, check=True
    )
    return [line for line in done.stdout.splitlines() if line]


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] != "--base":
        print(__doc__, file=sys.stderr)
        return 2
    problem = violation(_changed(argv[2]))
    if problem:
        print(f"protected-paths: {problem}")
        return 1
    print("protected-paths: the eval suite and the plugin are not changed together")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
