# Plan: register a repository that holds its own board

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: approved by the owner in session, 2026-11-13.
- Delivers: R1 (each artefact a committed file the next stage reads), R5 (one person may own every gate), R12 (parallel work in worktrees and subagents on one machine)

[`local-artefacts`](local-artefacts.md) let the board live in the repository where the work is done, but left that repository unable to take work. `asdlc register` refuses any repository with a `backlog/` folder ("is a board"), so its tasks can carry no project, and `asdlc next` and `asdlc review-next` skip every task without a registered project. The first project to keep its board beside its code (steg) could draft and accept work and then start none of it. This change lets a repository that holds its own board be registered like any other code repository, which is all the picker, the claim and the review queue need.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | `register` accepts the repository the board itself lives in, in either board mode: it records the slug and path on the machine, adds the slug to the board's projects and sets `asdlc.board` to the repository, so a task's worktree finds the board in the main checkout and not in its own copy of `backlog/`. It still refuses to register a board for a different board | R1, R12 |
| `tests/test_asdlc.py` | no | A repository with a local board is registered, a task in its project is offered by `next` and claimed into a worktree beside it, and a command run from that worktree changes the board in the main checkout. Registering a board against another board is still refused | R12 |
| `README.md`, `docs/guide.md` | no | `register` and "Where the board lives" say a repository that keeps its own board is registered too, and why | - |
| `CHANGELOG.md` | no | One entry | - |

## Order of work

1. This plan, committed before the code.
2. The tests, failing for the reason above.
3. The change to `register`.
4. The README, the guide and the changelog.
5. `./scripts/check`.

## Risks

- **A task's worktree holds its own copy of `backlog/`, and a command run there could treat that copy as the board.** Likely without care: the board is found from the folder you are in when nothing else names it. Setting `asdlc.board` at registration settles it, since worktrees share the repository's configuration and the configured board comes first. A test runs a board command from inside the worktree and checks where the change landed.
- **The rule loader and the board guard still treat a repository with `backlog/` as a board and nothing else.** Certain. `hooks/load_rules.py` delivers no rules for a file in such a repository, and `hooks/guard_board.py` does not keep edits there inside a claimed worktree or refuse a push to its default branch. Both are steering paths, so they need the eval gate and cannot ship with this change. Deferred as its own change; until then a same-repository board has the picker, claims and reviews but not the rules or the edit guard.
- **`asdlc doctor` on a local board with no scaffolding still fails on the missing marketplace.** Unchanged by this plan, and deferred with the hooks: a local board needs a decision on whether it carries the team plugin at all.
- **On a shared board in the code repository, asdlc refuses to work while the main checkout has uncommitted changes.** That is the shared board's existing rule, and work happens in worktrees, so the checkout stays clean. The guide says so.

## Proof

- `./scripts/check` passes, and its result is in the commit message.
- In steg, whose board is in its own repository, `asdlc register` succeeds, `asdlc repos` lists `bruk-io-steg`, and `asdlc doctor` no longer warns that no repository is registered.
