"""Person steps: what the engineer does between headless sessions, in their own terminal.

A step runs on the host, as the agent's engineer, after one session ends and before the
next resumes. It returns what the person did, in words, which the trace records beside the
board's state at that moment.
"""

import asdlc_eval as ev
import fixtures


def approve_waiting_plans(fixture: ev.Fixture, facts: dict[str, object]) -> str:
    """The engineer approves every plan their workers wrote that waits for approval, in one
    command with each plan's digest, as the orchestrate skill asks them to."""
    me = fixtures.machine_from(fixture, facts)
    mine = me.json("mine", "--as", str(facts["engineer"]))
    waiting = [t for t in mine["tasks"] if t.get("plan_hash") and not t.get("approval_holds")]
    if not waiting:
        return "nothing was waiting for approval"
    ids = [str(t["id"]) for t in waiting]
    hashes = [part for t in waiting for part in ("--plan-hash", str(t["plan_hash"]))]
    me.asdlc("approve", *ids, *hashes)
    return f"asdlc approve {' '.join(ids)} " + " ".join(hashes)

