# /// script
# requires-python = ">=3.15"
# ///
"""Say, once at the start of a session, whether the eval gate has passed on what is on disk (spec R22).

In a repository that has a gate (the plugin's eval suite and `scripts/eval`), one line of
context: pass, or why not, and that running the gate is a person's decision because it
spends tokens. A change that touches no steering path says nothing, and so does any other
repository. The check is `scripts/gate_evidence.py`, the same one the push guard asks.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from decision_log import Verdict, current_branch, decision, project_dir, record  # noqa: E402
from gate_evidence import State, check_change, has_gate, root_of  # noqa: E402

HOOK = "gate_status"


def context_line(state: State, line: str) -> str | None:
    """What the agent is told, None when there is nothing to say."""
    if state is State.NOT_NEEDED:
        return None
    if state in (State.PASS,):
        return f"asdlc: {line}."
    return (f"asdlc: {line}. Don't run `scripts/eval gate` yourself: a real run spends tokens, so a person decides. "
            "Pushing is refused until the gate has passed on the steering paths changed.")


def main() -> int:
    payload = json.load(sys.stdin)
    project = project_dir(payload)
    root = root_of(Path(str(payload.get("cwd") or project)))
    if root is None or not has_gate(root):
        return 0
    verdict = check_change(root)
    said = context_line(verdict.state, verdict.line())
    record(project, decision(datetime.now(), HOOK, "SessionStart", Verdict.ALLOW, verdict.line(), current_branch(project)))
    if said:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": said}}))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as error:  # a broken hook must be visible, not block the session
        message = f"failed and said nothing: {type(error).__name__}: {error}"
        print(f"asdlc: {HOOK} {message}", file=sys.stderr)
        print(json.dumps({"systemMessage": f"asdlc {HOOK} {message}"}))
        record(project_dir({}), decision(datetime.now(), HOOK, "", Verdict.ERROR, message, ""))
        code = 0
    raise SystemExit(code)
