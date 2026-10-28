"""A mistake made twice leaves one short rule in CLAUDE.md, and CLAUDE.md stays short."""

import re
from pathlib import Path

import asdlc_eval as ev
import fixtures

LOGIN_WITH_PRINT = fixtures.LOGIN.replace("    return check(user, password)\n", '    print(f"login attempt for {user}")\n    return check(user, password)\n')
LOGIN_WITH_LOGGING = fixtures.LOGIN.replace('"""Logins for acme/api."""\n', '"""Logins for acme/api."""\n\nimport logging\n\nlog = logging.getLogger(__name__)\n').replace(
    "    return check(user, password)\n", '    log.debug("login attempt for %s", user)\n    return check(user, password)\n')
RULE = "- Don't commit `print()` for debugging; use the `logging` module.\n"


def build(fixture: ev.Fixture) -> dict[str, object]:
    world = fixtures.solo(fixture, files={"login.py": LOGIN_WITH_PRINT})
    return world.facts(claude_before=(world.clone / "CLAUDE.md").read_text())


def reference(script: ev.Script, fixture: ev.Fixture, facts: dict[str, object], session: int) -> str:
    clone = Path(str(facts["app"]))
    script.read(clone / "login.py")
    script.write(clone / "login.py", LOGIN_WITH_LOGGING)
    claude = clone / "CLAUDE.md"
    text = script.read(claude)
    script.write(claude, text.replace("- Python 3.12, standard library only.\n", "- Python 3.12, standard library only.\n" + RULE))
    script.bash("python3 -m unittest -q")
    return "Replaced the print in login.py with a logging call, and added a rule to CLAUDE.md so it isn't committed again."


def collect(fixture: ev.Fixture, facts: dict[str, object]) -> dict[str, str]:
    tree = fixtures.tree(Path(str(facts["app"])))
    return {"login.py": tree.get("login.py", ""), "CLAUDE.md": tree.get("CLAUDE.md", "")}


def print_replaced_with_logging(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    text = found.files.get("login.py", "")
    if re.search(r"(?m)^\s*print\(", text):
        return False, "login.py still calls print()"
    if "logging" not in text:
        return False, "the print() is gone but login.py does not use logging"
    return True, "no print() in login.py, which uses logging"


def rule_added_to_claude_md(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    before = str(found.facts["claude_before"]).splitlines()
    added = [line for line in found.files.get("CLAUDE.md", "").splitlines() if line not in before and line.strip()]
    if not added:
        return False, "CLAUDE.md gained no line"
    if not any(re.search(r"\b(print|logging|debug)", line, re.I) for line in added):
        return False, f"CLAUDE.md gained lines but none about print or logging: {added[:2]}"
    return True, f"CLAUDE.md gained {len(added)} line{'s' * (len(added) != 1)}: {added[0].strip()[:100]}"


def claude_md_stays_short(found: ev.Outcome, case: ev.Case) -> tuple[bool, str]:
    before = str(found.facts["claude_before"]).splitlines()
    after = found.files.get("CLAUDE.md", "").splitlines()
    added = [line for line in after if line not in before and line.strip()]
    lost = [line for line in before if line not in after and line.strip()]
    if len(after) > 60:
        return False, f"CLAUDE.md is {len(after)} lines, over 60"
    if len(added) > 3:
        return False, f"{len(added)} lines were added; a rule is a line or two"
    if lost:
        return False, f"{len(lost)} existing lines were removed or rewritten, such as {lost[0].strip()[:80]!r}"
    return True, f"{len(after)} lines, {len(added)} of them new, none lost"
