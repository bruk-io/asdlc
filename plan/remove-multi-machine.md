# Plan: one orchestrator, no leads, heartbeats or reaping

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R12 (parallel work as subagents in worktrees on one machine; no coordination across machines), R9 and R2 (plans and acceptance stay a person's recorded action)

The third of three stacked changes in [`eval-suite.md`](eval-suite.md), and the one `plan/local-artefacts.md` deferred. Leads, heartbeats and reaping exist for engineers on several machines: a lead keeps one orchestrator in charge of an intent across them, a heartbeat says a claim is alive, and `reap` frees a claim whose machine went away. With one orchestrator launching its own workers none of the three has a job, and each costs the orchestrator a step every round. The eval suite change merged first (R23): the cases that exercised them are retired and no remaining case calls them.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | Removes `lead`, `lead-of`, `heartbeat` and `reap` with their logic (`LeadOf`, `lead_of`, `intent_above`, `Hold`, `Stale`, `stale_holds`, `reap_comment`, the lead key, `stale_after` and `approval_wait`), the `leads` list in `mine`, and the lead branch of `release` and of `holds`. A task's old `asdlc_lead` key is ignored, not an error. The default for `review_fallback_after` becomes 0, since the one orchestrator reviews with a reviewer subagent it launches itself, and no other engineer's machine is waited for | R12 |
| `skills/lead/SKILL.md` | removed | The lead's claim, contracts, change requests, plan checks and consistency review | R12 |
| `skills/orchestrate/SKILL.md` | no | One orchestrator: no reap, heartbeat or lead steps; a plan is checked against the spec and contract by the orchestrator itself; a review is launched at once for the engineer's own work | R9, R12 |
| `skills/write-spec/SKILL.md`, `skills/break-down-intent/SKILL.md`, `skills/capture-intent/SKILL.md` | no | No "lead" wording: the orchestrator writes the spec and drafts the children | R7, R8 |
| `agents/worker.md`, `agents/reviewer.md` | no | No `lead-of` step; the contract comes from the intent's linked documents | R9, R12 |
| `hooks/guard_board.py` | no | No special case for `reap` | R16 |
| `templates/board/asdlc.toml`, `templates/board/` | no | `stale_after` and `approval_wait` removed; `review_fallback_after` default 0 | R12 |
| `README.md`, `docs/guide.md`, `docs/repo-plugins.md`, `CHANGELOG.md` | no | The commands, settings and the lead skill's description removed | - |
| `tests/` | no | Tests of the four commands, of staleness and of the lead's board flow are removed with them; every other test stays as it is, and the demonstration of the orchestrator's day loses its reap, heartbeat and lead steps | R12 |

## Order of work

1. Remove the commands and their logic from `scripts/asdlc`, with the tests that exercise only them, one command at a time, running the unit tests after each.
2. Make `review-next` offer the engineer's own work at once (the `review_fallback_after` default), and say so in the orchestrate skill.
3. Rewrite the skills and agents; delete `skills/lead`.
4. Update the board template, the guide, the README and the changelog.
5. `./scripts/check`, and `scripts/eval validate`: the suite from the previous change must still validate against this branch, since it pins asdlc's interface.

## Risks

- **A board that already has a lead or a stale claim.** An `asdlc_lead` key stays in the task's file, ignored. A claim nobody works on is released by hand, `asdlc release`, as before; nothing else frees it now. That is the cost of removing `reap`, and with one orchestrator the claim is its own.
- **The review queue's default changes meaning.** With `review_fallback_after` at 0 the engineer's own work is offered for review as soon as it is In Review. Another engineer's orchestrator is still offered it first when there is one, because `review-next` prefers work by others.
- **The suite pins asdlc's interface.** Mitigation: step 5 runs `validate` against this branch. A case that calls a removed command would have been retired in the previous change.
- **Removing code from a 5,000-line script.** Each removal is followed by the unit tests for the commands that stay, so a function that something else used shows at once.

## Proof

- `./scripts/check` passes, including `scripts/eval validate` against this branch.
- `grep -rn "asdlc lead\|lead-of\|heartbeat\|asdlc reap\|stale_after" skills agents commands hooks scripts docs README.md templates` finds nothing. The suite is not in that list: the fixture's `asdlc.toml` still writes a `stale_after` line, which the plugin now ignores, and the small-request case checks it is not disturbed; changing them is a suite pull request of its own (R23).
- The orchestrate skill reads as one orchestrator's loop, and the day's demonstration (`tests/test_demo_orchestration.py`) still runs without the removed steps.
