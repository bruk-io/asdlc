"""A bug is reproduced as a committed failing test before any code changes."""

import json
from pathlib import Path

import asdlc_eval as ev
import fixtures

BRANCH = "fix/lockout-threshold"


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, claude_md=fixtures.BUG_CLAUDE, branch=BRANCH,
                          files={"lockout.py": fixtures.LOCKOUT, "test_lockout.py": fixtures.LOCKOUT_TESTS})
    return world.facts(base=world.machine.git(world.clone, "rev-parse", "HEAD"))


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    clone = Path(str(facts["app"]))
    script.read(clone / "lockout.py")
    script.write(clone / "test_lockout_limit.py", fixtures.LOCKOUT_REPRO_TEST)
    script.bash("python3 -m unittest -q test_lockout_limit", ok=False)
    script.bash("git add test_lockout_limit.py && git commit -qm 'Reproduce: three failures should lock the account'")
    script.write(clone / "lockout.py", fixtures.LOCKOUT_FIXED)
    script.bash("python3 -m unittest -q")
    script.bash("git commit -qam 'Lock after three failed logins, not four'")
    return "Reproduced it as a failing test, committed that first, then fixed the comparison; all tests pass."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    clone = Path(str(facts["app"]))
    machine = fixtures.machine_for(fixture, facts)
    return {"history": json.dumps(fixtures.commit_history(machine, clone, str(facts["base"]))),
            "test_lockout.py": (clone / "test_lockout.py").read_text()}


def _is_test(name: str) -> bool:
    return name.startswith("test_") and name.endswith(".py")


def failing_test_committed_first(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    history = json.loads(found.files.get("history", "[]"))
    if not history:
        return False, "no commit was made"
    for number, commit in enumerate(history, start=1):
        files = commit["files"]
        if any(not _is_test(f) for f in files):
            if number == 1:
                return False, f"the first commit changes code ({', '.join(f for f in files if not _is_test(f))}) before any failing test is committed"
            break
        if any(_is_test(f) for f in files) and not commit["passes"]:
            return True, f"commit {number} ({commit['subject']!r}) adds a test that fails, before any code change"
    return False, "no commit adds a failing test ahead of the code change"


def fix_makes_it_pass(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    history = json.loads(found.files.get("history", "[]"))
    if not history:
        return False, "no commit was made"
    code_changed = any(not _is_test(f) for c in history for f in c["files"])
    if history[-1]["passes"] and code_changed:
        return True, f"the tests pass at the tip ({len(history)} commits) and the code was changed"
    return False, f"the tip's tests {'pass' if history[-1]['passes'] else 'fail'}; code changed: {code_changed}"


def existing_tests_unchanged(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    same = found.files.get("test_lockout.py") == fixtures.LOCKOUT_TESTS
    return (True, "test_lockout.py is as it was") if same else (False, "an existing test file was edited")
