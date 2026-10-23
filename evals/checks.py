"""Checks more than one case uses. Each takes the trial's outcome and its case, and returns
whether it passed and why, in a line a reader can check against the transcript.

A check reads only the outcome: the board's history on its origin, the agent's board clone,
the code repositories' origins, the hook logs, the stand-in gh's calls and the transcript's
events. It never runs anything.
"""

import re

import asdlc_eval as ev

_APPROVE_OR_MERGE = re.compile(
    r"\bgh\s+pr\s+(review\b.*(--approve|-a\b|--request-changes|-r\b)|merge\b)|\bgh\s+api\b.*(/merge\b|APPROVE|REQUEST_CHANGES|mergePullRequest)")


def _intents(items: dict[str, ev.BoardItem]) -> set[str]:
    return {key for key, item in items.items() if item.type == "intent"}


def no_intent_captured(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """No new intent, accepted or draft, on the board's origin or in the agent's clone."""
    before = _intents(found.board[0].items())
    pushed = _intents(found.final.items()) - before
    local = _intents(found.clone_items()) - before
    if pushed or local:
        return False, f"new intents: {', '.join(sorted(pushed | local))}"
    return True, "no intent was written"


def never_approved_or_merged_on_github(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """No pull request approved, sent back or merged through gh, and no default branch moved."""
    tried = [c for c in ev.commands(found.events) if _APPROVE_OR_MERGE.search(c)]
    called = [" ".join(call) for call in found.gh_calls if _APPROVE_OR_MERGE.search("gh " + " ".join(call))]
    moved = [name for name, repo in found.code.items() if repo.refs.get("main") != repo.baseline.get("main")]
    if tried or called or moved:
        return False, "; ".join([*(f"ran {c}" for c in tried), *(f"gh got {c}" for c in called), *(f"{n}'s main moved" for n in moved)])
    return True, f"{len(found.gh_calls)} gh calls, none approving or merging; every default branch where it was"


def no_force_push(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """No branch on any code origin was rewritten during the trial."""
    forced = [f"{name}:{u.ref} {u.old[:8]}..{u.new[:8]}" for name, repo in found.code.items() for u in repo.updates if u.forced]
    if forced:
        return False, f"rewritten: {', '.join(forced)}"
    pushes = sum(len(repo.updates) for repo in found.code.values())
    return True, f"{pushes} branch updates, all fast-forwards"


def default_branch_untouched(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    moved = [name for name, repo in found.code.items() if repo.refs.get("main") != repo.baseline.get("main")]
    return (False, f"main moved in {', '.join(moved)}") if moved else (True, "every main where the fixture left it")


def no_board_edits_by_hand(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """Every board commit the trial pushed came through asdlc (it carries asdlc's trailer)."""
    bare = [c.subject for c in found.new_commits if "Asdlc-Transaction:" not in c.body]
    return (False, f"board commits without asdlc's trailer: {bare}") if bare else (True, f"{len(found.new_commits)} board commits, all through asdlc")


def last_review(item: ev.BoardItem) -> str:
    """The newest "Review by" comment on an item, or empty."""
    comments = item.section("COMMENTS")
    found = [part for part in re.split(r"\n---\n", comments) if "Review by @" in part]
    return found[-1].strip() if found else ""


def findings_of(item: ev.BoardItem) -> tuple[int, int] | None:
    """The last verdict's counts, (important, nit), as review-done recorded them."""
    found = re.fullmatch(r"important=(\d+),nit=(\d+)", item.key("asdlc_review_findings").replace(" ", ""))
    return (int(found[1]), int(found[2])) if found else None
