# Plan: the reviewer's git reads, from the first real eval run

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md)
- Status: approved by the owner in session, 2026-10-29 ("go for it")
- Delivers: R15 (an independent reviewer that can read the change)

The first real run of the suite showed `reviewer-false-alarm` failing 3 of 3 on a permission refusal: the reviewer ran `git -C <clone> diff origin/main...origin/task-1-count-failed-logins`. Two causes. `diff` and `log` were not in the allow rules for a registered clone. And the deny rule `Bash(git -C * -c*)` matches text, so a branch name with `-c` in it (`task-1-count-...`, a common shape) trips it.

## Files that change

| File | What changes |
|---|---|
| `scripts/asdlc` | `CLONE_GIT` gains `diff` and `log`, both read-only |
| `tests/test_asdlc.py` | A test that the clone allows `diff` and `log` and still refuses writes |
| `agents/reviewer.md` | Says why a branch name can trip the deny rules, and to diff in the review worktree against `HEAD` |
| `CHANGELOG.md` | One line |

## Order of work

1. Add the rules and the test.
2. Add the line to the reviewer agent.
3. Run `reviewer-false-alarm` and `reviewer-full-verdict` against the working copy, then `./scripts/check`.

## Risks

- `git diff` can run an external diff program. Low: the deny rules and the board guard already refuse `-c`, `--ext-diff` and `--textconv`, and the existing deny tests cover them.
- The deny rule's false positive on `-c` in a branch name stays. Narrowing it would weaken a security rule, so the agent is told how to avoid it instead.
- Not changed, deliberately: the tasks clone stays unreadable through git (`tests/test_guard_board.py` pins that), `approval-before-build` still sees one such refusal, and the two new skill descriptions still miss two `trigger-set` items (a wording change did not fix them).

## Proof

- `reviewer-false-alarm`: 0/3 before, 3/3 after, over three trials with the working copy as the plugin. `reviewer-full-verdict`: 2/3 both times; the one miss is the orchestrator's own `git diff` by branch name, not the reviewer's.
- `./scripts/check` passes.
- No file under `evals/` changes (R23).
