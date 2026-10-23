# Plan: evals in a devcontainer

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2), with its evals file [`spec/agentic-sdlc-plugin-evals.md`](../spec/agentic-sdlc-plugin-evals.md)
- Status: approved by the owner in the session on 2026-10-23, before building; it ships in the same pull request as the change.
- Delivers: R14 and R28 (the first task evals, deterministic checks only), R21 (the plugin under test is a read-only export, never the working copy), R23 (the suite under `evals/`, the protected path), R24 (every case cites its source), R29 (every trial's tokens, turns and time, and its cost at versioned API prices), and the stand-in R6 names for the change gate (reviewer recall and false refusals)

Play 08 of the playbook. Unit tests and the scripted demonstrations prove asdlc's commands; nothing yet proved what an agent does with them. This change adds evals that run real Claude Code agents headless against throwaway fixtures (a tasks repository with its board, a code repository, an engineer's machine), perform the person's steps between resumed sessions, and grade the outcome with deterministic checks outside the agent's reach. It follows Anthropic's eval practice: grader isolation, a reference and a null run for every case, trials with pass@k and pass^k and clustered standard errors, outcome and process cases, regression and capability suites, a baseline arm without the skills, durable counts with cost derived at report time, transcripts kept, the model as a parameter, a narrow tool scope, and cases only from incidents or a person. The image the agent runs in is the repository's dev container, so CI can reuse it later.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/eval` | yes | `validate`, `run`, `regrade` and `report`. The core over data: `parse_case`, `parse_stream` (events, counts by model with the cache-write lifetime, a resumed session's own share), `frontmatter` and `board_item` (its own Backlog parser, so the plugin never grades itself), `Outcome`, `shell_segments` and `runs_program`, `run_checks`, `validation_problems`, `pass_at_k`, `pass_hat_k`, `clustered_se`, `detectable`, `parse_prices`, `cost`, `summarise`, `report_lines`, `key_moments`, `sample`. The shell: `Fixture` and `Machine`, `Script` (the scripted reference and null runs, written as stream-json), `trial`, `collect` (the board's history, code origins with forced updates from their reflogs, hook logs, gh calls), `export_plugin`, `agent_settings`, `claude_arguments`, `claude_session` (native or `--container`) | R14, R21, R28, R29 |
| `evals/README.md` | yes | How to write a case: `case.toml`, `case.py`, the two-expert bar, reference and null runs, kinds and suites, what a run records | R23, R24 |
| `evals/prices.toml` | yes | API prices per million tokens, versioned, with the one-hour cache-write rate | R29 |
| `evals/fixtures.py`, `evals/steps.py`, `evals/checks.py` | yes | The usual world (`team`, acme/api with its plugin published, earlier rounds of work, the review scene); person steps (`approve_waiting_plans`); checks several cases share | R28 |
| `evals/cases/*/case.toml`, `evals/cases/*/case.py` | yes | Nine cases (below), each with its fixture builder, reference run and checks | R6, R24, R28 |
| `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json` | yes | Claude Code 2.1.309, uv 0.13.4 with Python 3.15, Node 22 with Backlog.md 1.55.2, git, bubblewrap, socat, ripgrep; multi-arch bases; no credentials | R14 |
| `tests/test_eval.py` | yes | The core on a recorded transcript and fixed board text; a forced push seen in a real bare repository; the agent's export leaving out the suite; regrading a stored outcome | R28, R29 |
| `scripts/check` | no | Runs `scripts/eval validate` after the tests | R14 |
| `CLAUDE.md` | no | `./scripts/check` includes the eval cases' reference and null runs | - |
| `docs/guide.md` | no | "Running evals" | - |
| `README.md` | no | The Evals section and its commands; what it does not do yet | - |
| `CHANGELOG.md` | no | Unreleased: evals | - |
| `.gitignore` | no | `.eval-results/` | - |
| `plan/evals.md` | yes | This plan | - |

### The first suite

| Case | Kind | Suite | Source |
|---|---|---|---|
| `reaped-worker-stops` | outcome | regression | Independent review B1 |
| `sent-back-resumes-branch` | outcome | regression | Independent review B2 |
| `approval-before-build` | process | regression | Independent review I7, and the brief's batched approvals |
| `reviewer-full-verdict` | outcome | regression | I3, Important 4 and stage metrics (the verdict's record); R15 and the pilot's guard (no approving or merging) |
| `grandchild-follows-lead` | outcome | regression | Second review round, Important 2 |
| `small-request-no-intent` | outcome | regression | The owner; evals spec, Should-not-capture |
| `reviewer-recall` | outcome | capability | Evals spec, Reviewer recall; the defect the review demonstration seeds |
| `reviewer-false-alarm` | outcome | capability | Evals spec, Reviewer false refusals |
| `trigger-set` | outcome | capability | The owner; evals spec, a should-stay-quiet case per skill |

## Order of work

1. The core on fixed data: cases, transcripts, board text, checks, statistics, cost; their unit tests.
2. The fixture: `Fixture`, `Machine`, `team` with acme/api's plugin published and the permission rules written, and the scripted `Script`.
3. One case end to end with `validate` (small-request-no-intent), then the rest, each validated as it is written.
4. `run` natively, `collect`, `report`; the first real run (case 6).
5. The image, built here; the container path up to sign-in.
6. The second real run (case 3); fixes from its transcript, `regrade`.
7. `./scripts/check` with `validate`, the docs, the pull request.

## Risks

- **Grader isolation natively.** A native agent runs on the same machine as the suite. It gets a fresh Claude Code configuration folder, its own home, the fixture in a temporary folder outside the repository, a read-only export of the plugin without `evals/`, `tests/` or the evals spec, and rules denying reads of this repository and the web tools; that is a convention, not an OS boundary. `--container` mounts only the fixture and the release, with Bash in Claude Code's sandbox (no network of its own).
- **A check that misreads the transcript.** Found in the first real run of case 3: a pattern for "ran a check or a commit" matched those words inside a plan's text. Checks now match the commands a shell line runs, with quotes and here-documents blanked (`shell_segments`), the reference run's plan carries those words so `validate` exercises it, and `regrade` re-judges stored outcomes after a fix.
- **Counts from resumed sessions.** A resumed session's `modelUsage` and `total_cost_usd` carry the whole conversation; the parser takes `model_usage_since_last_result`, this run's share. Without it, case 3's cost was counted as $0.78 instead of $0.50.
- **Background workers in a headless session.** Background tasks are switched off (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`), so the orchestrator's workers run in the foreground and the session waits for them. It changes timing, not what the skills ask.
- **Subagent events from their own transcripts.** Calls missing from the stream are added from the subagent transcripts, after the person steps, so an order check could miss one. In both real runs the stream carried every subagent call.
- **The suite pins asdlc's interfaces.** Reference runs call asdlc's commands, so a plugin change to one fails `validate`, and R23 keeps the cases out of that pull request. The eval change comes first in its own pull request, validated with `validate --plugin <the plugin branch>`.
- **Cost.** Real runs count against the owner's subscription. Each case sets `max_turns`, `max_budget_usd` and a timeout; the trigger set reads one turn per request.
- **Variance.** One trial per case says little; the report says so, and states the smallest change a run of its size can detect.

## Proof

- `./scripts/check` passes: the artefacts, every test including `tests/test_eval.py`, and `scripts/eval validate`, every case's reference run passing every check and its null run failing at least one.
- The image builds here (`docker build -t asdlc-evals:local .devcontainer`, linux/amd64), and runs its tools; the container path (`run --container`) runs a session up to sign-in.
- Two real runs, natively, one trial each:

| Case | Result | Turns | Tool calls (errors) | Tokens (sonnet 5.5: input, output, cache read, cache write) | Time | Cost at API prices |
|---|---|---|---|---|---|---|
| `small-request-no-intent` | passed | 3 | 2 (0) | 6, 279, 35,111, 17,912 | 6s | $0.0780 |
| `approval-before-build` | passed after the check fix (`regrade`) | 18 | 63 (14) | 118, 18,230, 1,145,190, 66,830 | 156s | $0.5024 |

## Departures from the approved plan

- **`regrade`**, not in the plan: the case 3 run failed on a check bug, not on the agent, and re-judging its stored outcome cost nothing. The earlier verdict is kept in `trial.json` under `earlier_checks`.
- **The real runs ran natively, not in the container.** The image builds here and Docker runs, but this environment's Claude Code sign-in is supplied by the host and has no token to hand a container (`claude auth status` in the image: not logged in). With `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` set, `--container` passes it through. Since the image built here, no build-only CI job was added, as the plan said; the build here is linux/amd64 only.
- **Permissions.** Each session gets the rules `asdlc permissions --write` writes on a pilot machine, prompts answered "no" (`--permission-prompts none`), and a permission mode per case, `acceptEdits` by default: in the pilot a person accepts the orchestrator's own edits, and the small-request case needs that.
- **The sandbox runs only in the container.** This host has neither bubblewrap nor socat; natively, sandbox settings are added only when both are present.
- **Case 4's pull request** is on GitHub in name only: `gh` is a stand-in that records every call, and the code origin is a local path, so a reviewer following its agent file skips the comment. The check reads approve and merge attempts from both the transcript and the stand-in's log.
- **The trigger set** reads only each request's first turn (`max_turns = 1`).
- **`validate --plugin`**, not in the plan, for the interface risk above.
- **The protected-paths job fails on this pull request**, as the plan foresaw: `evals/` arrives with the runner and its docs, which count as the plugin's side. Later plugin changes can't touch `evals/`.

## What the real transcripts showed

- Background workers were refused `git -C <worktree> ls-files` and any `cd <worktree> && ...` line: `asdlc permissions` has no rule for them, so with nobody to answer, the planner of TASK-2 wrote placeholder paths until the orchestrator sent it back to read the files. 14 of case 3's 63 calls failed, most of them so.
- Each worker first ran `asdlc record-check` from the tasks clone, was told to run it from the worktree, and did.
- The orchestrator asked `asdlc-plugin status` for the slug before the path, ran `asdlc doctor` unprompted, and resumed its phase 1 workers with `SendMessage` after the approval rather than launching new ones.
- The orchestrator asked for approval once, naming both plans with their digests and the one command, and nothing was edited, checked, committed or pushed before the approval.

## Left for later

- Merge gating on "no worse than the release, beyond the measured spread" (R22), once a baseline run exists.
- The private holdout (R30).
- The CI workflow running the same image, with a sign-in secret, and an arm64 build of the image.
- Ablations, each component removed in turn (R25).
- An LLM judge from a different model family, validated against human labels, for what no check can judge.
- Time from incident to eval as a stats metric, and eval pass rate per change in `asdlc stats` (play 08).
- Permission rules for the commands workers were refused (above): a plugin change.
