# Plan: the test-edit guard on bug tasks, and repeated findings turned into rules

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: approved by the owner in the session on 2026-10-23 ("yes and do so autonomously"), before building; it ships in the same pull request as the change.
- Delivers: R13 (test files cannot be edited while fixing a bug), R10 (a mistake made twice gets a line), R15 (review findings ranked and recorded), R16 (a refusal says why and the route past it), R26 (every hook decision logged)

The second review of asdlc against Anthropic's AI-native SDLC playbook (2026-10-23) found two gaps small enough to fix in one change.

1. **The test-edit guard never runs on board work.** It judges `fix/` branches only, but a claim names its branch `task-<id>-<slug>`, so a bug task on the board can edit the test that is meant to prove its fix (playbook play 07; tracked as M5 in `plan/pilot.md`). Worse, the guard finds the repository from the session's working directory, and board workers stay in the tasks clone and edit their worktree by absolute path, so even a `fix/` worktree is judged against the tasks clone's branch.
2. **A finding made twice changes nothing.** Plays 04 and 09 say a mistake flagged a second time gets its correction written into the agent's instructions. Reviews record the policies their findings cite (`review-done --policy`), and `asdlc stats` counts them, but nothing turns a repeat into a rule.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | The claim's worktree marker, `.asdlc-task`, also records the task's `type`. `review-done` reports `repeats`: for each policy the verdict cites, the other tasks whose last review cited it too, from `earlier_citations` (pure), in its JSON and as a line naming them | R13, R10, R15 |
| `hooks/guard_test_edits.py` | no | A write is a bug fix when its branch starts with `fix/` or the worktree's marker says its task's type is `bug`. The guard finds the repository from the path written to, not the session's directory: the file's own folder for the file tools, and for a shell command the session's directory plus every `-C`/`--in` folder and every absolute path the command names. `decide_file` and `decide_command` take the bug task's id; `strongest` (pure) picks the verdict across several repositories. The denial names the bug task | R13, R16, R26 |
| `agents/reviewer.md` | no | After `review-done`, when it reports a repeat: read the earlier reviews, and when a finding is the same mistake, file one draft `rule-change` task saying which rule file gets which line and why, unless an open draft already covers it. The draft is a note for a person, who adds the line through a pull request to the tasks repository and archives it. Its writes are now `review-done`, a pull request comment and those drafts | R10, R15 |
| `skills/orchestrate/SKILL.md` | no | Step 11: tell the engineer about any `rule-change` draft the reviewer filed, and how it is acted on: a pull request to the tasks repository, then archiving the draft | R10 |
| `templates/board/plugins/team/skills/testing/SKILL.md` | no | The guard covers bug tasks as well as `fix/` branches, so a reproducing test goes in a new test file | R13 |
| `README.md` | no | The feedback-loop row says bug tasks | - |
| `plan/pilot.md` | no | M5 resolved by this change | - |
| `tests/test_hooks.py` | no | Bug-task worktrees denied through Edit and shell writes from the tasks clone, `-C`, `--in` and absolute paths; ordinary tasks allowed; a marker with no type allowed; `strongest` | R13 |
| `tests/test_asdlc.py` | no | The marker's `type`; `earlier_citations`; `review-done` reporting a repeat and none on a first citation | R10, R13 |
| `CHANGELOG.md` | no | Unreleased: both fixes | - |
| `plan/bug-guard-and-repeat-findings.md` | yes | This plan | - |

Nothing under `evals/` changes (R23). The reviewer's new command, `asdlc board task create ... --draft`, must already be allowed by the rules `asdlc permissions` writes and by the board guard; `test_every_command_the_agents_give_is_allowed` proves it.

## Order of work

1. Failing tests for the guard: a repository with a worktree whose marker says `bug`, edited from another directory by absolute path, through Edit, `sed -i` with an absolute path, `git -C <worktree> checkout -- <test>` and `asdlc record-check --in`.
2. The guard: the bug test, the repository from the path, `strongest`. Its tests pass, and the existing `fix/` tests pass unchanged.
3. Failing tests for the marker's `type`, `earlier_citations` and `review-done`'s `repeats`; then `scripts/asdlc`.
4. The reviewer, the orchestrator skill, the testing skill, README, pilot plan and changelog.
5. `./scripts/check`, including `scripts/eval validate`.

## Departures, after the independent review

- **A `rule-change` draft isn't accepted with `asdlc accept`.** The first version told the engineer to accept it, but `accept` takes intents only. The draft is now a note: the engineer adds the line through a pull request to the tasks repository (how plugin changes go) and archives the draft. Making it an intent would send a one-line rule through a lead, a spec and a breakdown.
- **The guard reads more forms and copies by destination.** The review found that `git --git-dir/--work-tree`, attached `-C`, relative folders and `~` paths escaped the guard, and that `cp <existing test> <new test>` and `pip install ... && pytest <test>` were refused. The guard now reads those forms, splits a line into its simple commands outside quotes, and judges `cp` and `install` by their destination only. Tests for each.

## Risks

- **Worktrees claimed before this change have no `type` in their marker.** The guard allows them, as before. Every claim rewrites the marker, including a resumed one, so the next claim of a task covers it.
- **A reproducing test in an existing file is refused on a bug task.** The guard judges whole files: a test file that exists on the base branch can't change while fixing a bug, so the reproducing test goes in a new file, as on `fix/` branches today. The testing skill says so, and the denial says to add a new test file or ask the person.
- **Finding the repository from the command's words.** A shell write to a test through a path the guard can't see (a variable, a relative path after a `cd`) is missed, as before: it is a guardrail, not a wall. Absolute paths, `-C` and `--in` cover how agents are told to work.
- **Repeats are by policy, not by mistake.** Two findings citing `testing-python` may be different mistakes. `review-done` only reports the earlier reviews; the reviewer reads them and files a draft only when it is the same mistake, and a person decides whether the draft becomes work. The last review's policies are what a task keeps, so an earlier round on the same task isn't counted.
- **Noise.** A reviewer filing a draft for every repeat could flood the board. One draft per mistake, none when an open `rule-change` draft covers it, and drafts are archived by a person in one command.

## Proof

- `./scripts/check` passes: artefacts, every test, and `scripts/eval validate`.
- The new guard tests deny an edit to an existing test in a bug task's worktree made from the tasks clone, and allow the same edit in an ordinary task's worktree.
- `review-done` on a second task citing the same policy reports the first task as a repeat, and on a first citation reports none.
