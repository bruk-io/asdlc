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


# The two refusals Claude Code writes as a tool's result when nobody can answer a permission
# prompt, as the first real run of approval-before-build recorded them: the first for a call
# that needed approval, the second for a tool or command the session may not use at all.
_REFUSAL = re.compile(r"Permission for this tool use was denied\b|Permission to use [^\n]{1,500}? has been denied\b")
# A simple command runs cd or git: after any VAR=value assignments, the program's name or path.
_RUNS_CD = re.compile(r"^(?:\w+=\S*\s+)*cd\b")
_RUNS_GIT = re.compile(r"^(?:\w+=\S*\s+)*(?:\S*/)?git\b")


def _runs(line: str, program: re.Pattern[str]) -> bool:
    return any(program.search(part.lstrip("({ ")) for part in ev.shell_segments(line))


def no_permission_denials(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """No tool call, the orchestrator's or any subagent's, was refused for want of a permission,
    and no Bash line changes directory and runs git, which Claude Code always asks about.

    From the first real run of approval-before-build: background workers were refused
    `cd <worktree> && ... git ...` and `git -C <worktree> ls-files`, with nobody there to
    approve, and a planner wrote placeholder paths because it couldn't list its worktree.
    Checks see the outcome, not the trial's counts, so the denials are counted from the
    refusals the harness recorded as tool results; every denial in a session's
    `permission_denials` is one of them.
    """
    calls = {e.id: e for e in found.events if e.kind == "tool" and e.id}
    refused = [e for e in found.events if e.kind == "result" and _REFUSAL.match(e.text.lstrip())]
    cd_git = [e for e in found.events if e.kind == "tool" and e.command and _runs(e.command, _RUNS_CD) and _runs(e.command, _RUNS_GIT)]
    if not refused and not cd_git:
        bash = sum(1 for e in found.events if e.kind == "tool" and e.command)
        return True, f"no refusals among {len(calls)} tool calls; none of {bash} Bash lines runs cd and git together"

    def shown(event: ev.Event) -> str:
        call = calls.get(event.id, event)
        what = call.command.splitlines()[0][:120] if call.command else call.name or "a tool"
        return f"{'a subagent' if event.parent else 'the main agent'}: {what}"
    refused_ids = {e.id for e in refused}
    problems = [*(f"refused, {shown(e)}" for e in refused), *(f"cd and git, {shown(e)}" for e in cd_git if e.id not in refused_ids)]
    more = f"; and {len(problems) - 6} more" if len(problems) > 6 else ""
    return False, f"{len(refused)} permission refusals, {len(cd_git)} cd-and-git lines: {'; '.join(problems[:6])}{more}"


def last_review(item: ev.BoardItem) -> str:
    """The newest "Review by" comment on an item, or empty."""
    comments = item.section("COMMENTS")
    found = [part for part in re.split(r"\n---\n", comments) if "Review by @" in part]
    return found[-1].strip() if found else ""


def findings_of(item: ev.BoardItem) -> tuple[int, int] | None:
    """The last verdict's counts, (important, nit), as review-done recorded them."""
    found = re.fullmatch(r"important=(\d+),nit=(\d+)", item.key("asdlc_review_findings").replace(" ", ""))
    return (int(found[1]), int(found[2])) if found else None


def skill_exists_with_owner_and_source(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    """A policy skill was written under .claude/skills with its frontmatter, and names the owner and the source the case gave
    (`owner` and `source` in the fixture's facts)."""
    text = found.files.get("skill", "")
    if not text:
        return False, "no .claude/skills/*/SKILL.md was written"
    problems = []
    if not re.match(r"(?s)---\n(?=.*?^name:\s*\S)(?=.*?^description:\s*\S).*?^---", text, re.M):
        problems.append("no name and description in the frontmatter")
    if str(found.facts["owner"]) not in text:
        problems.append("the owner is not named")
    if str(found.facts["source"]) not in text:
        problems.append("the source is not given")
    return (False, "; ".join(problems)) if problems else (True, f"{found.files['skill_path']} has its frontmatter, owner and source")
