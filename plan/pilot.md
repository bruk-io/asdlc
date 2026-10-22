# Plan: pilot readiness

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: approved by the owner in the session before building, as `CLAUDE.md` now says; it ships in the same pull request as the change.
- Delivers: R2 (approving and merging stay a person's recorded action), R12 (each worker and reviewer in a worktree that gets the repository's conventions), R15 (the agent that reviews a change cannot approve it), R16 (the guard blocks with the reason and logs it), and the first measurement toward R19

The last pull request of the pilot. #16 to #20 built the board, the team plugin, orchestration, onboarding and cross-machine review, each against a slightly different picture of the others; combining them showed where they disagree. This change makes them agree, closes the gaps the review pull request left open (nothing stopped an agent approving or merging), and adds what a team needs to start and to judge the pilot: `asdlc doctor` says whether a machine is ready, `asdlc stats` says how the work is going, and `docs/guide.md` is the page a joining developer reads.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | `board_setting`, the one board lookup order; `changes-requested` and `review-passed` in the labels `init-board` writes; the event log (`Attempt`, `event_line`, `parse_events`) written by `claim`, `next`, `review-next` and `lead`; `doctor` (facts gathered by a shell, findings decided by `diagnose`); `stats` (snapshots from the board's history, `history`, `board_stats`, `percentile`) | R2, R12, R19 |
| `scripts/asdlc-plugin` | no | `board_for_repo` uses `asdlc.board_setting`: `--board`, then `ASDLC_BOARD`, then `git config asdlc.board` | R12 |
| `hooks/load_rules.py` | no | `ASDLC_BOARD` before the repository's `git config asdlc.board` | R12 |
| `hooks/guard_board.py` | no | Refuses `gh pr review --approve`/`--request-changes` (`-a`, `-r`), `gh pr merge`, and `gh api` calls that merge or submit an APPROVE or REQUEST_CHANGES review, GraphQL included | R2, R15, R16 |
| `skills/orchestrate/SKILL.md` | no | Onboarding decided by `asdlc-plugin status --json`, waiting when another onboarding is open | R12 |
| `agents/reviewer.md` | no | Reviews in a detached worktree of the registered repository, `<repo>.worktrees/review-<task>-<reviewer>` | R12, R15 |
| `CLAUDE.md` | no | "The loop": each change carries its plan, approved in the session, in the same pull request | - |
| `docs/guide.md` | yes | The page for a developer joining the pilot | - |
| `README.md` | no | `doctor`, `stats`, the event log, the lookup order, the guard's new refusals, a link to the guide | - |
| `CHANGELOG.md` | yes | 0.1.0: #16 to #20 and this change | - |
| `tests/test_asdlc.py` | no | `board_setting`, the event log, `diagnose`, `history` and `board_stats` on fixed inputs; the lookup order, the event log and `stats` against real repositories; the init-board label expectation | R2, R12, R19 |
| `tests/test_asdlc_plugin.py` | no | The lookup order through `status` | R12 |
| `tests/test_load_rules.py` | no | The environment before git config; rules delivered in a detached review worktree | R12 |
| `tests/test_guard_board.py` | no | Every approval and merge form refused, comments and reads allowed, an unseen body allowed and said | R2, R15, R16 |
| `tests/test_demo_orchestration.py` | no | Each demonstration machine keeps its event log in its own folder | - |
| `tests/test_demo_pilot.py` | yes | The review story with onboarding in it, then `doctor` on a ready and a broken machine, then `stats` | R19 |

## Order of work

1. The lookup order: `board_setting` in `asdlc`, used by `resolve_board` and `asdlc-plugin`; the rule loader reordered; a test in each.
2. The labels, with the two `init-board` tests' expected lists updated.
3. The guard's `gh` refusals and their tests.
4. The orchestrate skill's onboarding step, the reviewer's worktree and a rule-loader test for it, `CLAUDE.md`.
5. The event log in `claim`, `next`, `review-next` and `lead`.
6. `doctor`: `diagnose` over `Facts` with a test per finding, then `gather`.
7. `stats`: `history` and `board_stats` on fixed snapshots, then the shell reading `git log` and `git cat-file`.
8. The demonstration, the guide, the README, the changelog, `./scripts/check` and `claude plugin validate .`.

## Risks

- **Changing the lookup order changes which board a session uses.** Only where `ASDLC_BOARD` and a repository's `asdlc.board` disagree, which `asdlc` already resolved this way; the rule loader and `asdlc-plugin` now agree with it. Tested in all three.
- **A guard that parses `gh` can be walked around.** It is a guardrail, like the rest of the guard: it covers `gh pr` and `gh api` (REST and GraphQL), allows with a visible message when it can't see a request body, and the reviewer's prompt still says comment only.
- **Doctor's plugin checks depend on `claude plugin list --json` and `claude plugin marketplace list --json`.** Their shape was read from Claude Code 2.1.308. When `claude` is missing or prints something else, doctor warns that it couldn't check rather than fail. Auto-update is reported on only when the marketplace entry says `autoUpdate: true`; otherwise it warns with how to turn it on.
- **Stats from commit times.** Committer clocks, as for `reap`; a skewed machine skews its spans. Snapshots are per commit, so two changes in one commit read as one.
- **The event log is per machine.** Lost races per claim are this machine's, which is what an engineer can act on; the board-wide numbers come from the board.

## Departures from the brief

- `doctor` also fails when `asdlc` itself isn't on `PATH` (the skills call it by name), warns when the asdlc plugin isn't installed (unless it is loaded with `--plugin-dir`), and lists leftover review worktrees, `<repo>.worktrees/review-*`, beside the two leftovers the brief names, since the reviewer now makes them there.
- Levels chosen where the brief didn't say: a `devs/<name>.yaml` that doesn't set `review` fails (the brief asks that it sets it); a missing marketplace or team plugin fails; auto-update off, no authoring kit, no `asdlc.toml` and leftovers warn.
- `doctor` runs `asdlc-plugin check` with `--repo` when the plugin's repository is registered on the machine, so layers and rules are checked against its files too.
- `stats` fetches but never rebases or pushes, so it works on a clone with uncommitted changes; it reads `origin/main`.
- Review wait is read from every commit that changes a task's status line to In Review (the signal PR 2b reads with `git log -G`), for every entry into In Review rather than only the latest, each paired with the next review claim. In Review to Done runs from a task's first entry into In Review.
- An onboarding's time runs from the newest claim in that repository at or before its "Add the <slug> plugin" commit, since nothing records which task triggered it.
- The event log records refusals too: errors, a held or reserved task, and `next` or `review-next` at the cap (with no task). "No work available" isn't an attempt and isn't logged.
- The guard also refuses the GraphQL mutations that merge or approve; a `gh api` call whose body it can't see (`--input`, `-F field=@file`) is allowed with a message, as the guard does whenever it can't tell.
- The two `init-board` tests' expected label lists now include `changes-requested` and `review-passed`. That updates an expectation to the new behaviour; it doesn't weaken the test.
- `README.md`'s first line said every change starts as an intent; it now says what `CLAUDE.md` says.
- The demonstration uses small stand-ins for `claude`, `gh` and `uv` on each machine's `PATH`, so each machine can have its own installed plugins and sign-in; `claude plugin validate` goes to the real CLI when it is installed.
- Tests keep every event log in a temporary folder: `test_asdlc`'s machine without configuration and each demonstration machine set `XDG_STATE_HOME`.

## Proof

- `./scripts/check` passes, including the new logic on fixed inputs and the commands against real repositories and the backlog CLI.
- `claude plugin validate .` passes.
- `ASDLC_DEMO=1` on `tests/test_demo_pilot.py` prints `asdlc doctor` on a ready machine (exit 0) and on one with problems (exit 1), and `asdlc stats` after the review story; the pull request quotes it.
