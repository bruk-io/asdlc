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

## Fixes from the independent review

An independent review of this branch ran its claims as experiments (two machines, one bare board origin, a code repository) and found two blockers, ten important problems and nine minor ones. Each fix below started from a regression test that reproduces the experiment and failed, then the change, then the test passing. Every board change an agent makes still goes through `_transact` (or `board_command`'s equivalent) with a holder check where a worker acts.

| Finding | What changed | Regression test |
|---|---|---|
| B1: a reaped worker could finish a task someone else held, through `asdlc board` and `record-check` | `asdlc finish <id> --as <worker> [--branch] [--pr] --notes` sets In Review, records the branch and pull request and appends notes in one `_transact`, refusing unless the worker holds the task In Progress (`holder_refusal`); it also resubmits after changes, removing `changes-requested`. `record-check` takes `--as` and refuses before running the check, and again before recording it. The guard refuses In Progress and In Review, `-a`/`--assignee` on `task edit`, `task archive`/`demote`, and the review labels through `backlog` and `asdlc board`, naming the command to use. | `test_asdlc.ReapedWorkerTest` (three tests); `test_guard_board.BoardStatusTest.test_denies_an_agent_changing_who_holds_a_task_or_where_it_is` |
| B2: a reaped changes-requested task was rebuilt from main and force-pushed over the pull request's branch | The claim writes `asdlc_branch` in its own commit; `make_worktree` resumes the recorded branch: from `origin/<branch>` when pushed, fast-forwarding a local copy that is behind, and from the default branch only when nobody pushed it. `reap` and `release` keep a changes-requested task reserved for its author's engineer (`kept_on_release`). The worker agent never force-pushes (rebase onto `origin/<branch>`, merge the default branch once pushed), and the guard refuses force pushes to code repositories. | `test_asdlc.ResumedBranchTest` (two tests); `test_guard_board.PushTest.test_denies_force_pushing_a_task_branch` |
| I1: an interrupted command wedged the clone or pushed a phantom claim later | Every asdlc board commit carries an `Asdlc-Transaction` trailer, and `_change` writes a marker (`.git/asdlc-transaction.json`, with the commit it started from) for the change's lifetime. `_catch_up` never pushes earlier commits: it drops unpushed commits that are asdlc's own (trailer, or inside an interrupted marker's range) and refuses with what to do when there are others. `_require_ready` undoes an interrupted change's working-tree files. SIGTERM and SIGHUP unwind like Ctrl-C, so `_change` drops the change. `board_command` squashes backlog's commits into one with the trailer. `LOCK_WAIT_SECONDS` is 45, and the message says another command holds the lock. | `test_asdlc.InterruptedCommandTest` (SIGTERM, SIGKILL, a foreign commit, the lock) |
| I6: heartbeats weren't tied to liveness | The claim writes the first `asdlc_heartbeat`. `heartbeat` on the worker's task once it left In Progress is a no-op, exit 0, saying to stop. The orchestrate skill heartbeats what its running agents hold at the top of every round from `mine`, never from a detached loop, surfaces failures, and adopts its engineer's In Progress tasks on start. | `test_asdlc.HeartbeatLivenessTest` |
| I7: plan approval wasn't enforced | `asdlc approve <id>...` (guard refuses agents) writes `asdlc_plan_approved_by` and a "Plan approved by @<engineer>" comment, refusing a task with no plan. `record-check` and `finish` refuse size 2 and up without it (`approval_refusal`). The guide, the orchestrate and plan-change skills and the worker agent say so. | `test_asdlc.PlanApprovalTest`; `test_guard_board.BoardStatusTest.test_denies_an_agent_approving_a_plan` |
| I9: `record-check` couldn't show where it ran | It runs only when the working directory is in the worktree whose `.asdlc-task` names the task, and records the worktree, branch, commit and whether it had uncommitted changes (`Where`, `check_note`). | `test_asdlc.RecordCheckWhereTest` |
| I4: after `accept` the lead tracked old draft ids | `accept` comments the mapping on the intent and writes `asdlc_accepted_from` on each promoted item. `held_item` resolves an old draft id to the worker's task for `heartbeat` and `release`; `lead_of` resolves a gone draft id; `mine` lists a lead's `accepted_from`; `lead` refuses an old draft id the worker's lead came from unless `--new`. The skills read ids from `mine` each round. | `test_asdlc.AcceptedIdsTest` |
| I5: `accept` left grandchildren behind | `accept` walks the draft subtree level by level, re-parenting each child under its newly accepted parent, then remaps dependencies across all of them. | `test_asdlc.AcceptSubtreeTest` (three levels) |
| I2: reviews starved | `build_refusal`: with `review: true`, `next` won't take the last free slot while a review waits for the engineer (`_waiting_reviews`, fallback included) and none of their reviewers holds one. `mine` reports `reviews_waiting` and `slot_left_for_review`. The orchestrate skill reviews before it picks. | `test_asdlc.ReviewSlotTest` |
| I3: reviewers judged team code by asdlc's own `REVIEW.md` | `templates/board/plugins/team/review.md`, a generic team policy (passes, Important and Nit, a nit cap, evidence, the size-1 check); a repository plugin may add `review.md`. `review-next` names the files that exist as `policies`; the reviewer agent reads those and never `${CLAUDE_PLUGIN_ROOT}/REVIEW.md`. | `test_board_scaffolding.TemplatesTest.test_the_team_review_policy_judges_team_code_not_asdlcs_own`; `test_asdlc.ReviewPolicyTest`; `ReviewCommandTest.test_claims_the_oldest_review_and_says_where_to_review_it` |
| I8: the guard couldn't see Backlog.md's MCP tools | By the owner's decision, no MCP: asdlc works through the `backlog` CLI only. `doctor` warns when `~/.claude.json` (user and local scope) or the board's `.mcp.json` configures a Backlog.md MCP server, saying the CLI is the only way and the server bypasses the board's rules; the guide says not to add it. No hook matcher for MCP tools: an MCP matcher written first was taken out. | `test_asdlc.DoctorTest.test_a_backlog_mcp_server_is_reported` |
| I10: background workers would stop at permission prompts | The owner's goal: no prompts in normal work. `asdlc permissions [--write] [--json]` (`permission_rules`, `merge_permissions`) prints the allow rules this machine needs: `Bash(asdlc *)`, `Bash(asdlc-plugin *)`, backlog's read commands, `Bash(git *)`, `Bash(gh pr create *)`/`view`/`comment`, `Bash(uv run *)`, an exact rule for each part of each registered repository's verified commands (`commands.toml`), and `Edit(//<folder>/**)` plus `additionalDirectories` for the worktree folders beside each registered clone and the tasks clone. `--write` merges them into `~/.claude/settings.json` (or `$CLAUDE_CONFIG_DIR/settings.json`), keeping everything there, after a timestamped backup, and refuses a file that isn't JSON; the guard refuses it from agents. `doctor` warns, naming the missing rules and the command. Rule syntax checked against code.claude.com's permissions page. No hook answers `ask`. | `test_asdlc.PermissionRulesTest`, `PermissionsCommandTest`, `DoctorTest.test_permissions_for_background_workers`; `test_guard_board.BoardStatusTest.test_denies_an_agent_writing_the_persons_permissions`, `test_the_guards_never_ask`; `test_demo_pilot` (each machine runs `--write`, then doctor passes) |
| M2: guard shell gaps | `~` expanded in `cd` and `git -C`; shell keywords stripped; combined `-lc`/`-ec`; `xargs <cmd>`; a `cd` or `-C` to a variable allows with a message. A command's verdict is its first refusal, else the first thing it couldn't tell. | `test_guard_board.ShellFormsTest` |
| M4: the same worker name in two sessions | A claim of a task already held under that name is refused, saying another session may be using it. | `test_asdlc.SameWorkerNameTest` |
| M6: long commands | The worker agent, the team's testing skill and the onboard-repo skill say to give `record-check` and `verify-command` a long Bash timeout or run them in the background. | (documentation) |
| M9: the board's `.gitignore` | `init-board` adds `.gitignore` with `.asdlc/`, or appends the line to an existing one. | `test_board_scaffolding.InitBoardScaffoldingTest.test_the_board_ignores_the_hook_decision_log` |
| M10 | Covered by I6. | |

### Departures

- B1: the brief named `--branch` and `--pr` on `finish`. `--branch` is optional, since B2 records the branch at claim time; given, it must match. `--notes` is required, so every hand-off says what was built. The guard also refuses the review labels (`review-passed`, `changes-requested`) through `asdlc board`, which B1 didn't name, since adding `review-passed` by hand would skip review. It refuses assignee changes only on `task edit`: a lead still reserves a child with `-a @<engineer>` when drafting it.
- B1 and I9 landed in one rewrite of `record_check`, so I9's test was written after its code; it fails against the code before B1, which had no `--as` and ran anywhere.
- I1: both a trailer and a marker, since an interrupted command can leave backlog's own commit (no trailer yet) before asdlc squashes it. A commit made by hand on top of an interrupted change, before the next asdlc command, is inside the marker's range and is dropped with it; this is noted in the guide.
- I6: the claim writes `asdlc_heartbeat` too, so the first heartbeat is visible on the task, not only in its commit time.
- I7: `approve` takes several ids, so the orchestrator's batch is one command; it refuses a task with no plan. Phase 2 starts with a baseline `record-check`, which is where an early launch is refused.
- I4: `lead --new` is new: once a lead's intent was accepted, its old draft id is ambiguous, so leading the new draft with that id needs saying so.
- I8 and I10 changed mid-task on the owner's decision ("No MCP. Just the CLI."): the brief's MCP matcher in the guard was built and then taken out with its tests, which tested only that matcher, and I10 became a command that writes the rules instead of a documented snippet.
- I10: `Bash(git *)` rather than rules scoped to the worktrees: a rule can't scope by working directory, workers run `git -C <worktree>`, and a `*` before the subcommand draws a startup warning; the guard bounds what git may push. `doctor` treats a `defaultMode` of `acceptEdits` as covering edits and `bypassPermissions` as covering everything, and reads `CLAUDE_CONFIG_DIR` when set; the demonstration machines each have their own.
- Tests whose expectations changed with the behaviour: two guard cases that allowed `-s "In Progress" -a ...` and `-s 'In Review'` moved to the refused list; the review tests and demonstrations hand work to review with `finish` after `approve`, and expect the branch the claim recorded (`task-1-rate-limit`) rather than one passed by hand; `MineAndRecordCheckTest` approves the plan before recording a check. None is loosened.
- The team testing skill's evidence step now uses `asdlc record-check`; an existing board keeps its old copy (init-board never overwrites), which the changelog says.

### Left as tracked risks

- **M1, no escape hatch in a registered clone.** Every session with the plugin is guarded there; the guide says to unset `asdlc.board` for the while. A per-session switch is later work.
- **M3** is covered by B1.
- **M5, the test-edit guard on board branches.** Unchanged; it judges `fix/` branches only.
- **M7, version skew** between the `asdlc` on `PATH` (a clone) and the installed plugin's skills. The guide says to keep them at one release; `doctor` doesn't compare them yet.
- **M8, effort per launch.** The orchestrator passes `asdlc route`'s effort when it launches an agent; nothing checks the launch used it.
- **Permission behaviour of background agents** changes between Claude Code versions (stall or auto-deny); `asdlc permissions --write` and doctor's check aim at no prompts either way. A command an agent writes differently from the rules (an extra flag on a verified command, say) can still prompt.
