"""A small request doesn't become an intent: the one-line change is made, and nothing goes on the board."""

import re
from pathlib import Path

import asdlc_eval as ev
import fixtures


def build(fixture: ev.Fixture) -> dict[str, object]:
    team = fixtures.team(fixture, agent="kyle", devs={"kyle": "name: kyle\nworkers: 2\nreview: true\n"},
                         items=[fixtures.Spec("Rate limit the login endpoint", size="size-2", project="acme-api")], publish=False)
    return team.facts()


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    settings = Path(str(facts["board"])) / "asdlc.toml"
    text = script.read(settings)
    script.write(settings, re.sub(r'review_fallback_after = "[^"]*"', 'review_fallback_after = "15m"', text))
    return "Set review_fallback_after to 15m in asdlc.toml; it's yours to commit and push."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    return {"asdlc.toml": (Path(str(facts["board"])) / "asdlc.toml").read_text()}


def setting_changed(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    text = found.files.get("asdlc.toml", "")
    wanted = re.search(r'(?m)^review_fallback_after\s*=\s*"15m"\s*$', text)
    kept = re.search(r'(?m)^stale_after\s*=\s*"2h"\s*$', text)
    if wanted and kept:
        return True, "review_fallback_after is 15m and stale_after is still 2h"
    return False, f"asdlc.toml is now: {text.strip()!r}"


def no_new_board_items(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """Nothing pushed to the board at all, and nothing new in the clone: a settings edit isn't board work."""
    added = set(found.clone_items()) - set(found.board[0].items())
    if found.new_commits or added:
        return False, f"{len(found.new_commits)} board commits pushed; new items in the clone: {sorted(added)}"
    return True, "the board is as the fixture left it"
