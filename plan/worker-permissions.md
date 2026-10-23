# Plan: background agents that never need a prompt or a `cd`

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: approved by the owner in the session on 2026-10-23, before building; it ships in the same pull request as the change.
- Delivers: R12 (parallel workers each in their own worktree, which they must be able to work in unattended), R13 (one check command, recorded from wherever the worker is), R16 (a refusal says why and the route past it), and the stand-in evidence R14 asks for: the first real eval run's tool errors, fixed at their causes

The first real run of the `approval-before-build` eval (plan/evals.md, "What the real transcripts showed") passed, but 14 of its 63 tool calls failed, and one planning worker wrote a plan with placeholder file paths because it couldn't list its worktree. Every error came from three causes in the plugin, not in the model: the agent files told workers to `cd <worktree> && ...`, which Claude Code always prompts for when the line also runs git (and nobody is there to answer a background worker's prompt); `asdlc permissions` had no rule for the read-only git commands a planner reaches for first (`git -C <worktree> ls-files`); and `asdlc record-check` worked only from inside the worktree. This change removes the need for `cd` altogether, allows the read-only git a worker or reviewer uses, and lets `asdlc-plugin` take the slug the orchestrator already has.

## The first run's tool errors, by cause

Case `approval-before-build`, trial 1, plugin `b2a2cff` (`.eval-results/20261023T051741Z-b2a2cff-with-plugin`), 63 calls, 14 errors, 7 of them permission denials:

| # | Who | Call | Error | Cause |
|---|---|---|---|---|
| 1, 2 | both planners | `cd <worktree> && cat .asdlc-task && asdlc board task view ... && git ls-files \| head -50` | denied: "changes directory before running a version-control command" | `cd` with git in one line: Claude Code prompts for it whatever the allow rules say. worker.md said to run asdlc "from the worktree" |
| 3, 4 | both planners | `git -C <worktree> ls-files` | denied: requires approval | no allow rule for `ls-files` (or any read-only git beyond status, diff, log, show) |
| 5, 6 | both planners | Read on the worktree folder | EISDIR | no way left to list the files; nothing told them about Glob |
| 7 | orchestrator | `asdlc mine --json \| python3 -c ...` | denied: python3 requires approval | piping asdlc's JSON through an interpreter no rule allows |
| 8, 11 | both builders | `asdlc record-check ...` from the tasks clone | refused: not a task's worktree | record-check took the worktree only from the working directory |
| 9, 13 | both builders | `cd <worktree> && asdlc record-check ... -- python3 -m unittest -q` | exit 1 | the deliberately failing test before the fix (the plan's red step): expected, not a defect |
| 10, 12 | both builders | `cd <worktree> && git add ... && git commit ...` (one also `python3 -m unittest` bare) | denied | `cd` with git again; worker.md's commit step used `git -C`, but its record-check step had taught `cd` |
| 14 | builder 1 | `git -C <worktree> push -u origin HEAD; which gh` | exit 1 | `which gh` exits 1 when gh is missing: the worker probed for something the claim could have told it |

Not counted as errors, but the same causes: `asdlc-plugin status acme-api --json` (the slug, where it wanted a path) failed inside a compound line whose last command succeeded; the TASK-2 planner's first plan named `<module defining login(user, password)>` and the orchestrator had to send it back.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | `permissions --write` also makes each additional directory that doesn't exist yet (see the second run, below). `READ_ONLY_GIT` (ls-files, grep, blame, cat-file, ls-tree, merge-base, rev-list, describe, show-ref, `remote get-url`) added to the worktree rules and the registered clone's, each with its bare form as before. A global `--in <folder>`, before or after the subcommand, that every command uses as its working directory, and `record-check <id> --in <worktree> --as <worker> -- <command>`; the refusal outside a worktree names `--in`. A `github` field on the claim and review-claim reports: the origin's `owner/name` when it is on GitHub and `gh` is installed, else null, from `github_repo` (pure) | R12, R13, R16 |
| `scripts/repo_slug.py` | no | `github_repo(remote)`: `owner/name` for a github.com remote, else None | R12 |
| `scripts/asdlc-plugin` | no | `status`, `scaffold` and `verify-command` take a repository path or a registered slug, and `check`/`publish --repo` too; `repo_argument` (pure) decides, and an unknown name is refused with the registered slugs | R16 |
| `agents/worker.md` | no | Where each command runs: asdlc from anywhere, record-check with `--in`, git always as `git -C <worktree>`, one command per call, files listed with `git -C <worktree> ls-files`, searched with `git grep` and read with Read; never `cd`, never an interpreter in a pipe; the pull request with `gh pr create --repo <github>` only when the claim gave `github` | R12 |
| `agents/reviewer.md` | no | The same for the reviewer: `git -C`, Read, no `cd`; comment on the pull request only when the claim gave `github` | R12, R15 |
| `skills/orchestrate/SKILL.md` | no | Run every command from the tasks clone; `asdlc-plugin status` with the slug or the path; the launch prompt carries `github`; read JSON yourself rather than pipe it into an interpreter | R12 |
| `skills/lead/SKILL.md`, `skills/onboard-repo/SKILL.md` | no | Where their commands run; `git -C` and Read to read a repository; `<repo>` may be the slug | R12 |
| `tests/test_asdlc.py` | no | `permissions --write` makes the missing worktree folders; `--in` for record-check (from the tasks clone, before or after the id) and as a global option; the refusal names `--in`; `github_repo`; the claim report's `github` | R13 |
| `tests/test_asdlc_plugin.py` | no | `repo_argument` over paths, registered slugs and unknown names; `status` by slug against a real registry | R16 |
| `tests/test_guard_board.py` | no | The walk over every command in the skills and agents: no `cd` in any of them; every part of every agent command, and of the orchestrator's skills, covered by an allow rule, with no `cd` exemption; Claude Code's cd-with-git prompt modelled and asserted absent; the new read-only git allowed bare and with arguments, in worktrees and the clone, and still not the clone's writes | R12, R16 |
| `README.md`, `docs/guide.md` | no | `--in`, the read-only git in the permissions list, `asdlc-plugin` taking a slug | - |
| `CHANGELOG.md` | no | Unreleased: these fixes | - |
| `plan/worker-permissions.md` | yes | This plan | - |

Nothing under `evals/` changes (R23).

## Order of work

1. The transcript read and every error listed with its cause (above).
2. Claude Code's permissions page (code.claude.com/docs/en/permissions) for how compound commands and `cd` are matched: each part of a compound line must be allowed on its own; `cd` into an additional directory is read-only; but `cd` with git in one line prompts whatever the rules say, and an allow rule can't change that. So the fix is to remove `cd`, not to allow it.
3. `scripts/asdlc`: `--in`, the read-only git rules, `github`; their tests.
4. `scripts/asdlc-plugin`: slugs; its tests.
5. The agent files and skills; the walk's tests extended until they pass with no `cd` exemption.
6. `./scripts/check`, including `scripts/eval validate`.
7. One real run of `approval-before-build` against this branch's commit (`scripts/eval run --case approval-before-build --trials 1 --plugin <commit>`), compared with the first.

## Risks

- **`git grep -O<program>` runs a program.** The new `grep` rule allows it in a worktree, as the `*` in every existing `git -C <worktree>/* ...` rule already allows `-c` options before the subcommand. The rules make normal work prompt-free; they were never the boundary (the board guard, the sandbox and the worktree are). Noted, not changed here.
- **A slug that is also a folder name.** `repo_argument` treats a word with no `/` that is a registered slug as the slug, else as a path; a path with a slash, `.` or `~` is always a path. A folder in the working directory named exactly like a registered slug is read as the slug, which is the repository it names anyway.
- **`--in` on every command.** It changes only where the command looks for the board, the engineer and the code repository, as `cd` would; the guard reads the same command words, and record-check still refuses a folder that isn't the task's worktree.
- **The eval suite pins asdlc's interfaces.** The change only adds (`--in`, a report field, more rules, a slug where a path was), so the cases' reference runs are unchanged; `scripts/eval validate` proves it.
- **One trial.** A single run can't show a rate; it shows whether the causes above are gone. The report says so.

## Proof

- `./scripts/check` passes: artefacts, every test, and `scripts/eval validate`.
- The walk: every command the agents and skills give passes the guard, none has a `cd`, and every part of every agent and orchestrator command is allowed by a rule `asdlc permissions` writes.
- One real run of `approval-before-build`, natively, against this branch's commit: passed, with the tool calls, the errors by cause, the turns, the tokens and the cost next to the first run's (63 calls, 14 errors, 18 turns, $0.50).

## The second run

`approval-before-build`, trial 1, plugin `cf0cdf7` (this branch before the fixes below), natively, `.eval-results/20261023T132106Z-cf0cdf7-with-plugin`:

| Run | Result | Turns | Tool calls | Errors | Permission denials | Tokens (sonnet 5.5: input, output, cache read, cache write) | Agent time | Cost at API prices |
|---|---|---|---|---|---|---|---|---|
| First (`b2a2cff`, main) | passed after the check fix | 18 | 63 | 14 | 7 | 118, 18,230, 1,145,190, 66,830 | 156s | $0.5024 |
| Second (`cf0cdf7`) | passed, every check | 14 | 52 | 4 | 2 | 80, 11,335, 695,778, 70,309 | 152s | $0.4048 |

No `cd`, no refused git, no record-check from the wrong folder, no slug error, no `which gh`, and both plans named real files the first time. Its four errors:

| # | Who | Call | Error | Cause | Fixed |
|---|---|---|---|---|---|
| 1, 2 | both planners | `cat <worktree>/.asdlc-task` | denied: "may only concatenate files from the allowed working directories: tasks, tasks.worktrees" | `<clone>.worktrees` was in `additionalDirectories` but didn't exist when the session started (the first claim makes it), and the session left it out of the folders Bash may read. The Read tool still read there | here, after the run: `permissions --write` makes the folders |
| 3 | planner of TASK-1 | Glob | "No such tool available: Glob" | this Claude Code build has no Glob tool; the agent file told the worker to use it | here, after the run: the agents list and search with `git -C <worktree> ls-files` and `git grep`, and read with Read |
| 4 | builder of TASK-2 | `asdlc record-check ... -- python3 -m unittest -q` | exit 1 | the deliberately failing test before the fix: expected | - |

The fixes for errors 1 to 3 came after the one model run this change was allowed, so no run proves them; their unit test (the folders exist after `--write`) and the walk do.

## After review: git that runs a program

The orchestrator's review of #26 found the gap this plan had left open: the `*` in every `git -C <worktree>/* <subcommand> *` allow rule matches any text, so `git -C <wt>/x -c core.fsmonitor=<cmd> status`, `git -C <wt>/x config core.fsmonitor <cmd> status`, `git grep -O<program>` and the like ran without a prompt under rules asdlc wrote. Closed on this branch:

| File | What changes | Requirements |
|---|---|---|
| `hooks/guard_board.py` | `git_program_refusal`, `git_config_writes`, `env_names`, `git_env_refusal`: agents are refused global `-c`, `--config-env`, `--exec-path=<dir>`; `git config` writes (reads stay allowed); `grep -O`/`--open-files-in-pager`; `--upload-pack`, `--receive-pack` and `--exec` on fetch, pull, push, clone, ls-remote, archive and submodule; `-u` on clone and ls-remote; `--ext-diff` and `--textconv` on any subcommand; clone's `-c`/`--config`, clone and init `--template`; `rebase -x`/`--exec`; `difftool`, `mergetool`, `submodule foreach`, `bisect run`, `filter-branch`, `instaweb`; and any `GIT_*` variable set in front of a command, through `env`, or with `export`/`declare`. Short options are parsed per subcommand, attached and clustered (`-ccore.x=y`, `-Ovim`, `-nO`, `-uevil`, `-ix`), and a value-taking option's value is skipped (`grep -e -O` is a pattern). Each refusal names the form and says to run git plainly or ask the person | R16 |
| `scripts/asdlc` | `GIT_DENY`, written as `permissions.deny` by `asdlc permissions` (deny beats allow) and checked by `asdlc doctor` in every permission mode: `git -c*`, `git -C * -c*`, `--config-env`, `--exec-path=`, `grep -O`/`--open-files-in-pager`, `--upload-pack`, `--receive-pack`, `--exec`, clone and ls-remote `-u`, clone `-c`/`--config`, `--template`, `--ext-diff`, `--textconv`, `rebase -x`, `difftool`, `mergetool`, `submodule foreach`, `bisect run`, `filter-branch`, `instaweb`, `git config` and `git -C * config`, `env GIT_*`, `env * GIT_*`, `export GIT_*` | R16, R17 |
| `agents/worker.md`, `agents/reviewer.md` | Run git plainly; a refused commit message that quotes such a flag is reworded | R12 |
| `tests/test_guard_board.py` | Every form above refused with its reason (attached, clustered, through `sh -c`, `record-check`, loops and `env`); plain git (`push -u`, `fetch -u`, `grep -e -O`, `rebase -X ours`, `commit -c`, `log -O`, config reads) allowed; every form written on its own matched by a deny rule, including the allow rule's span that let `config` through; no command an agent or skill gives matched by any deny rule; the known limits written down | R16 |
| `tests/test_asdlc.py` | The deny rules in the settings, merged after the person's own, and reported missing by doctor even under `bypassPermissions` | R16 |
| `README.md`, `docs/guide.md`, `CHANGELOG.md` | The deny rules and the guard's new refusals | - |

Checked against code.claude.com/docs/en/permissions: deny and ask rules apply when any subcommand of a compound line matches, including inside a subshell, a command substitution or a loop body; a `*` matches any text; a trailing ` *` also matches the bare command only when it is the only wildcard; deny rules match past any leading assignment, while an allow rule never matches past an assignment of a variable outside Claude Code's known-safe set, so `GIT_PAGER=x git log` already prompts and is refused in the background.

### Departures from the review's list

- **`-u` only on clone and ls-remote.** On `push` it is `--set-upstream`, which every worker runs (`git push -u origin HEAD`), and on `fetch` it is `--update-head-ok`; neither runs a program, and pull has no `-u`. `--upload-pack`, `--receive-pack` and `--exec` are refused on all of them.
- **More than the list**, the same class: `git config` writes (the allow rules' `*` let `git -C <wt>/x config core.fsmonitor <cmd> status` through), `rebase --exec`, `bisect run`, `filter-branch`, `instaweb`, `clone -c`/`--config`/`--template` and `init --template`, `archive --exec`, and `--textconv` everywhere.
- **Every `GIT_*` assignment is refused**, not only those in front of git: they change nothing but git, and a bare `export GIT_PAGER=...` changes every git after it.

### Risks

- **A deny rule matches text, not options.** A commit message or a grep pattern that quotes ` -c `, `--exec`, ` config ` or `-O` after `grep` is refused with Claude Code's generic denial; the guard, which parses the command, allows it. The worker agent says to reword the message. The tests keep the known cases in `_DENY_RULE_FALSE_POSITIVES` and check that no command the agents and skills give is denied.
- **A deny rule can't see inside a cluster** (`-nO`, `-ix`); only the guard catches those, and the guard is a hook (it allows on its own internal error, with a message).
- **Case.** `Bash(git -c*)` must not match `git -C ...`. The permissions page says the words before the first `*` are matched as written; WebFetch domains are the only case-insensitive match it names. Not exercised by a model run here.
- **asdlc's own git** sets `GIT_CONFIG_*` and `core.hooksPath` to turn hooks off on board commits, inside the `asdlc` process, which neither the guard nor the permission rules see. No skill, agent or team template tells an agent to set a `GIT_*` variable or pass `-c` (the walk checks every command they give against the guard and the deny rules).

## Departures from the plan

- **The folders `permissions --write` makes, and no Glob in the agents' guidance**: not in the approved plan; the second run found both, and they share its root cause (a background worker stopped by something it can't ask about).
- **Glob and Grep stay in the agents' `tools` lists**: a session that has them may use them; the guidance no longer depends on them.
