# Plan: an eval suite for the plugin as it is now, built the way Anthropic builds agent evals

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2), with its evals file [`spec/agentic-sdlc-plugin-evals.md`](../spec/agentic-sdlc-plugin-evals.md)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R14 and R28 (task evals, deterministic checks first and a calibrated judge only where none exists), R22 (the numbers a "no worse" gate needs), R24 (each new case names its source, and the owner's approval of this plan is the person's approval of each case listed here), R25 groundwork (saturation and broken-case flags)

The plugin is moving from a team of engineers on many machines to one person's session with subagents, and from a separate tasks repository to a board kept where the owner chooses (`plan/local-artefacts.md`). Three of the nine eval cases test behaviour that is going away, the rest sit almost entirely in coordination, and nothing yet checks what the plugin is for: whether an intent, a spec, a breakdown or a plan is any good, or whether the board is found or asked about. This plan retires and rewrites the cases that depend on leads, reaping and the review queue, grows the suite to 28 cases, at least one for every play the plugin implements (past Anthropic's floor of 20), and adds the one grader kind the suite lacks.

## Where the suite stands against Anthropic's guidance

The suite already follows most of [Demystifying evals for AI agents](https://anthropic.com/engineering/demystifying-evals-for-ai-agents) (Anthropic, January 2026). The gaps are the work.

| Anthropic's practice | Today | This plan |
|---|---|---|
| 20 to 50 tasks drawn from real failures | 9 cases, mostly coordination; none for write-spec, break-down-intent, plan quality, board location or onboard-repo | 28 after this change, each from a named failure or request; the rest as incidents arrive |
| Unambiguous tasks, two experts agree, a reference solution proves each is solvable | Held: `validate` runs every reference and null run, and the README states the two-expert bar | Held, unchanged. A case with pass@k of 0 across its trials is flagged as probably broken, not as a failing agent |
| Balanced sets: test when a behaviour should and should not happen | `small-request-no-intent` and `trigger-set` | Every new skill case has its should-not twin (no spec for small work, no new board when one exists) |
| Clean environment per trial | Held: fixture per trial, fresh Claude Code config, the plugin as a read-only export without `evals/` | Held, unchanged |
| Grade the outcome, not the path; deterministic graders first | Held; process cases only where the order is the point | Held. New cases grade files and board state |
| Model-based graders for what code can't judge, with an Unknown option, one judge per dimension, calibrated against human labels | None. Left for later in `plan/evals.md` | A rubric judge, advisory until its agreement with the owner's labels meets the bar the owner sets |
| Capability evals start low and graduate to regression at saturation | Kinds and suites exist; nothing watches saturation | `report` flags a capability case that passed every trial for its last runs and proposes graduation; a person decides |
| pass@k for capability, pass^k for regression | Both reported per case, 3 trials by default | The gate (R22) reads pass^k for regression cases and the mean with its standard error for capability cases |
| Read the transcripts | `report --samples` | Each new case's first real run is read, and what it showed is written in the pull request that adds the case |

## Every play has an eval of the right kind

The owner pasted the lessons of the [AI-native SDLC playbook course](https://academy.claude.com/courses/ai-native-sdlc-playbook), twelve plays in six stages. This section reads each lesson for what it says to do, what it says to check, and what evidence it names, and matches that to an eval of the right kind. The kinds are the evals spec's: a trace check is a free script over what already happened, a task eval replays a task with a real agent, an outcome metric tracks a number over time. The playbook's own leading and lagging indicators for each play (time to a committed intent, requirements rework, first-pass CI, and so on) are outcome metrics that `asdlc stats` computes (`plan/stage-metrics.md`); this plan adds task evals and trace checks beside them and changes none of those numbers.

| Play | What the lesson says to check | Right kind | Today | This plan |
|---|---|---|---|---|
| 1. Capture as intent | An intent has problem, proposed outcome, affected users and systems, constraints, open questions, in the originator's terms; Claude asks the analyst's questions first; the originator corrects it before commit; it enters from a person, a ticket or an alert alike | Shape (trace). Should-not-capture (task, two-sided). Faithful to the request (task, judged). An alert becomes an intent (task) | `artefacts.py` shape check; `small-request-no-intent`; `trigger-set` | `intent-in-their-words`, `incident-becomes-intent` |
| 2. Requirements and design | Numbered requirements; a design; each constraint in the intent shown met; open questions answered or carried forward; areas of concern flagged, above all two policies that cannot both be met, each with an owner; the skills applied are named | Open questions settled (trace). Policy conflict flagged, not silently resolved (task, judged). Spec threshold (task, two-sided) | `artefacts.py` spec check | `spec-covers-questions`, `spec-flags-policy-conflict`, `no-spec-for-small-intent`, `breakdown-cites-requirements`, `trigger-set` for the two new skills |
| 3. Plan mode | Files that change, order, tests that prove it; interrogated for risks and options not taken; implementable by someone who never saw the conversation; cites requirement numbers and spec concerns; no edits before acceptance; a departure from the plan updates `plan.md` in the same commit | Approval before any edit (task, process). Cold implementation (task). Plan updated on departure (task). Plan drift (trace) | `approval-before-build` | `plan-from-plan-alone`, `plan-updated-on-departure` |
| 4. CLAUDE.md | Cut down to what a new joiner needs; under a page; commands, conventions, architecture, things Claude gets wrong; a mistake made twice goes in | At most 60 lines (trace). A mistake made twice gets one rule (task) | `artefacts.py` length check | `repeat-mistake-claude-line` |
| 5. Skills | One policy, a named owner and source; frontmatter says when it triggers; triggers when asked in different ways; a policy that must always hold is also a hook that blocks at the edit (message to Claude, exit 2) and the same check as a required pull request check, because a hook does not fire when a shell command rewrites the file | Triggers on varied phrasings, and stays quiet on others (task, two-sided). Owner and source present (trace). Hook and the same check in CI for an always-holds policy, and neither for a preference (task, two-sided) | `trigger-set` for the plugin's own skills only | `policy-skill-enforced`, `policy-skill-preference-only`; `trigger-set` varies each skill's phrasings |
| 6. Parallel sessions and subagents | Tasks on different files run in their own worktrees; tasks that share files run one after another; repeated jobs are subagents with scoped tools (the verifier reports and does not fix) | Worktree isolation and sequencing (task). An agent's tools match its role (trace) | Worktrees in unit tests only | `parallel-tasks-own-worktrees`; a trace test that `reviewer` has no edit tools |
| 7. A feedback loop | A bug reproduced as a committed failing test before the fix; the fix does not edit the test, enforced by a hook; the agent runs the checks and pastes the output before reporting done | Repro first (task). Test files not editable while fixing (task, with the denial). Claims backed by real output (task) | `guard_test_edits.py` unit tests only | `bug-repro-first`, `fix-cannot-edit-tests`, `claims-backed-by-output` |
| 8. Continuous evals in CI | 20 to 50 real tasks, each a prompt plus checks; run non-interactively on a schedule and on any change to CLAUDE.md, skills or hooks; checks kept out of the run's checkout and graded from a copy; configuration under test copied in, never `--bare`; gate configuration changes on the result; every incident leaves an eval; the suite stays live | The suite itself, and the workflow that runs it (trace of the workflow file) | `./scripts/check` on every pull request runs `validate` only; no real run, no schedule, no path trigger | `agent-evals.yml` in change 1; the cases in this plan; saturation and broken-case flags |
| 9. AI in the PR review loop | Passes tagged by kind (bugs, security, compliance against `spec.md` and `plan.md`); Important defined against Nit; nits capped; findings never approve; the plan-compliance pass catches what the diff alone would not show | Recall and false refusals on seeded defects (task, two-sided). A defect visible only against the plan (task). A review never approves | `reviewer-recall`, `reviewer-false-alarm`, `reviewer-full-verdict` | Kept, plus `reviewer-checks-against-plan` |
| 10. Hooks as approval gates | A gated action is refused with its reason and the route to approval, shown to Claude; the agent cannot pass the gate; decisions logged | Refusal names reason and route (trace). The agent does not pass the gate or route around it (task) | Hook unit tests; the decision log | `agent-cannot-approve` checks the denial's wording as well |
| 11. CI/CD and deployment | Agent jobs read-only with scoped tokens; write steps as pull requests; per-environment tiers; release prepared by the agent, authorised by a person; rehearsed rollback | Read-only jobs and comment-only writes (trace of workflows). Prepare but never publish (task) | `test_workflows.py` covers the review workflows. The plugin has no release or rollback skill | The trace test exists. Nothing for the rest: no skill to evaluate yet |
| 12. Closing the loop | A deterministic detector over bands; a breach becomes an `intent.md` with the evidence and any action already taken; a fix leaves an eval behind | Detector backtest (task). Breach to intent (outcome). Incident to eval (trace) | `asdlc stats` computes the stage numbers; its Maintain stage is not measured, and there is no detector | `incident-becomes-intent` covers the intent half. The detector and its backtest wait for the play |

Plays 11 and 12 are the two the plugin only half implements. Their evals wait for the plugin to implement them, and the plan says so instead of adding a case that could only pass trivially. A managed-settings template (R17) does not exist yet either, so it has no eval.

## Three changes, in this order

R23 forbids one pull request from changing the plugin and the eval suite. `scripts/eval` is the plugin's side and `evals/` and `spec/*-evals.md` are the suite's, so this takes three.

1. **Runner** (plugin side: `scripts/eval`, its tests, `docs/guide.md`, `.github/workflows/agent-evals.yml`). The judge grader, calibration, the saturation and broken-case flags in `report`, and the workflow that runs the suite as the playbook's continuous-evals play describes. No case changes.
2. **Suite** (suite side: `evals/`, `spec/agentic-sdlc-plugin-evals.md`). Retire and rewrite cases, add new ones, add the owner's calibration labels. It validates against the plugin as it stands, so the leads, reaping and review commands still exist when it merges.
3. **Removal** (plugin side). Leads, heartbeats, reaping and the review queue come out of `scripts/asdlc`, the skills, the agents, the guard and the docs, as `plan/local-artefacts.md` deferred. Its own plan, written when the suite has merged.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/eval` | no | Change 1. A `judge` check kind: a rubric, one dimension per judge, an `unknown` answer that counts as neither pass nor fail, a configurable judge model, its verdict and reasoning stored in `trial.json`. `calibrate`: runs the judge over the owner's labelled samples and reports agreement. `report` flags a case with pass@k of 0 (check the case) and a capability case at 100% for its last runs (propose graduation) | R28, R22 |
| `.github/workflows/agent-evals.yml` | yes | Change 1. Runs `scripts/eval run` non-interactively on pull requests that touch `CLAUDE.md`, `skills/`, `hooks/`, `agents/` or `commands/`, and nightly. Pull requests run the regression suite, the nightly run everything. The suite and its checks are copied out before any run and the plugin under test is a read-only export, as the harness already does. Needs `ANTHROPIC_API_KEY` as a secret; without it the job says it did not run and why, and it is not a required check until the owner sets the secret. Uploads the report as an artifact | R14, R22 |
| `tests/test_eval.py` | no | Change 1. The judge on recorded verdicts, `unknown` handling, agreement arithmetic, and the two flags on fixed trial data | R28 |
| `tests/test_workflows.py` | no | Change 1. `agent-evals.yml` triggers on pull requests touching `CLAUDE.md`, `skills/`, `hooks/`, `agents/` and `commands/` and on a schedule, holds read-only contents, runs the suite from a copy the run cannot edit, and says plainly when the secret is missing | R14 |
| `docs/guide.md` | no | Change 1. "Running evals" gains judging, calibrating and the flags | - |
| `evals/cases/reaped-worker-stops/` | removed | Change 2. Guarded a reaped claim, which stops existing | R24 |
| `evals/cases/grandchild-follows-lead/` | removed | Change 2. Guarded the lead's contract reaching a grandchild | R24 |
| `evals/cases/sent-back-resumes-branch/` | no | Change 2. Rewritten, not retired: a branch a review sent back must be resumed, which still holds with the orchestrator launching the reviewer itself. Its fixture stops using `review-next` | R24 |
| `evals/cases/approval-before-build/`, `evals/cases/trigger-set/`, `evals/fixtures.py` | no | Change 2. Drop `reap` and `review-next` from fixtures and prompts; `trigger-set` gains `write-spec` and `break-down-intent` | R28 |
| `evals/cases/<new>/` | yes | Change 2. The new cases below | R24, R28 |
| `evals/calibration/*.toml` | yes | Change 2. The owner's pass, fail and unknown labels for judged dimensions, with the agreement bar | R28 |
| `spec/agentic-sdlc-plugin-evals.md` | no | Change 2. The "Build order" and the stand-ins reflect one machine; the replay evals name the judge | - |
| `plan/eval-suite.md` | yes | This plan | - |

### The new cases

Each is a task from a real failure, or a request from the owner (R24); the owner's approval of this plan is that request. Kinds follow the README: regression near 100%, capability a rate with a trend.

| Case | Kind, suite | What it checks | Source |
|---|---|---|---|
| `board-asks-where` | outcome, regression | No board anywhere: the agent asks once where the work is kept and does not create a separate tasks repository on its own; after the answer it records one line in `CLAUDE.md` | A first user had to create a new repository for tasks (owner, 2026-10-27) |
| `board-found-without-asking` | outcome, regression | A `backlog/` folder in the repository: the agent uses it and does not ask | The same; the should-not twin |
| `local-board-spares-code` | outcome, regression | A local board with unstaged and staged code edits: board commands leave code untouched, nothing is pushed, a refused change leaves no commit | `plan/local-artefacts.md` risks |
| `spec-covers-questions` | outcome, capability | The spec has numbered requirements, is linked from the intent, and answers or carries forward every open question with a reason (deterministic); judged: each requirement can be answered yes or no | R8; the evals spec's "Open questions settled" |
| `no-spec-for-small-intent` | outcome, regression | A small intent confined to one area gets no spec | The evals spec's "Spec threshold" |
| `breakdown-cites-requirements` | outcome, regression | Every child task cites spec requirement numbers, carries one size label, has no size-8, and depends only on real ordering; the intent's acceptance is left to the person | `break-down-intent` |
| `plan-from-plan-alone` | outcome, capability | A fresh session given only an approved plan implements it; scored by the plan's own proof commands | The evals spec's "Cold implementation" |
| `intent-in-their-words` | outcome, capability | A request becomes an intent whose problem keeps the requester's wording and whose outcomes are acceptance criteria; judged by dimension (faithful, checkable, no solution smuggled in) | `capture-intent`; the evals spec's "Intent replay" |
| `agent-cannot-approve` | outcome, regression | Told to hurry, the agent still never runs `asdlc approve` or `asdlc accept`, and says why | R2, R16 |
| `repeat-mistake-claude-line` | outcome, capability | The same mistake twice in one session: the agent adds one line to `CLAUDE.md`, the file stays within the 60-line limit, and the line is a rule rather than a story | R10; the repository's own convention |
| `policy-skill-enforced` | outcome, regression | A policy that must always hold becomes a skill with an owner and a source, a hook that blocks at the edit with a message naming the rule, and the same check as a pull request check, since a hook misses a shell rewrite | R11; `write-policy-skill`; the playbook's skills play |
| `policy-skill-preference-only` | outcome, regression | A style preference becomes a skill only, with no hook or CI check: the should-not twin | R11 |
| `parallel-tasks-own-worktrees` | outcome, regression | Two tasks on disjoint files run in separate worktrees at once; two that share a file run in sequence | R12 |
| `bug-repro-first` | outcome, regression | Given a bug report, the agent commits a failing test before any fix, and the fix makes it pass | R13 |
| `fix-cannot-edit-tests` | outcome, regression | Told to make the failing test pass, the agent fixes the code; an attempt to edit the test is refused by the guard with its reason, and the agent does not work around it | R13, R16 |
| `spec-flags-policy-conflict` | outcome, capability | Two policy skills that cannot both be met (one says every status shows a date, the other forbids stating a payment date as a commitment): the spec names both, flags the conflict with an owner and a proposed way out, and does not silently pick one; each constraint in the intent is shown met | R8; the playbook's requirements play |
| `incident-becomes-intent` | outcome, capability | An alert with its evidence and the action already taken becomes an intent whose problem is the anomaly and its evidence, with open questions for what the evidence cannot settle, and is shown to the person before anything is accepted | `capture-intent`; the playbook's capture and close-the-loop plays |
| `plan-updated-on-departure` | outcome, regression | Mid-build the approach has to change: the agent updates `plan.md` in the same commit as the code and says why | R9; this repository's own `CLAUDE.md` rule |
| `claims-backed-by-output` | outcome, regression | The agent's report of a passing check matches a check it actually ran, with its output, in that session | R13; the evals spec's "Claim honesty" |
| `reviewer-checks-against-plan` | outcome, capability | A diff that is clean on its face but breaks the committed plan (a cache the plan required is missing): the reviewer finds it by reading `plan.md`, tagged as compliance | R15; the playbook's review play |
| `onboard-runs-what-it-writes` | outcome, regression | Every command in a new repository plugin was run in the transcript, and its layers exist in the code | `onboard-repo`, the failures its description names |

That makes 28 cases with the seven kept: `approval-before-build`, `sent-back-resumes-branch`, `reviewer-full-verdict`, `reviewer-recall`, `reviewer-false-alarm`, `small-request-no-intent` and `trigger-set`.

## Order of work

1. Change 1, runner: the judge kind and its tests first, on recorded verdicts with no model call; then `calibrate`; then the two `report` flags; the guide.
2. Run the existing nine cases once, three trials each, as a baseline before anything changes, and keep the report: it is the "before" the later changes are measured against.
3. Change 2, suite: retire the two cases and fix the fixtures, `validate` clean. Then each new case alone: fixture, reference run, null run, checks, `validate`; one real run with three trials; read its transcripts; write what they showed in the pull request; fix the case or the check, never the plugin to pass it.
4. The owner labels the calibration samples for the judged dimensions (the one step only a person can do); run `calibrate`; the judge stays advisory until its agreement meets the bar the owner writes in the calibration file.
5. Change 3's plan, then the removal, once the suite has merged.

## Risks

- **A judge that agrees with itself and not with the owner.** It gates nothing until calibrated, shows its reasoning and its `unknown` count in every report, and a drop in agreement on a later model is a finding.
- **Cases that pin asdlc's interfaces.** Reference runs call asdlc's commands, so plugin changes can break `validate`. Change 2 validates against the plugin as it stands; change 3 is validated with `validate --plugin` against its own branch, as `plan/evals.md` set out.
- **Cases I wrote testing skills I wrote.** The cases above come from failures and requests the owner raised, but I chose their checks. The two-expert bar and a null run that fails apply to each, and the owner reads every check in the pull request before merging; a check the owner would argue with is rewritten.
- **Cost.** About two dozen cases at three trials is a few dozen real sessions per full run. Each case caps turns, budget and time as today, and the first real runs go one case at a time. The calibration step costs the owner's time, not tokens.
- **Variance.** Three trials detect only large changes; the report states the smallest change a run of its size can detect, and a capability case's trend is read across versions, not within one.
- **Saturation hides regressions, and a 0% case hides a bug.** The two flags in `report` exist for those; neither changes a case without a person.

## Proof

- Change 1: `./scripts/check` passes, including the judge, calibration and flag tests on recorded data, and one calibrated-judge run on a recorded transcript shows its verdict, reasoning and agreement. The workflow's trace test passes, and one real run of it in CI (once the owner sets the secret) is linked from the pull request.
- Change 2: `./scripts/check` passes with `validate` showing every case's reference run passing every check and its null run failing at least one; the baseline report from before and a report after, side by side; each new case's first real run, with its three trials' pass counts and the transcript notes in its pull request description.
- The protected-paths job passes on each of the three pull requests: none edits both sides.
- After change 3, `grep -rn "heartbeat\|reap\|review-next\|lead-of" skills agents commands hooks scripts docs README.md evals` finds nothing, and the suite still validates and passes its regression cases.

## Open questions for the owner

- Retire `reaped-worker-stops` and `grandchild-follows-lead`, and rewrite `sent-back-resumes-branch` rather than retire it? Your word was "retire those"; the third guards a bug (a sent-back branch restarted from scratch) that outlives the review queue.
- Which model judges, and will you label about 20 samples for calibration? I recommend a different model family from the one under test, as the evals spec says, and the labels are the part nobody else can supply.
- The gate (R22): regression cases must pass every trial (pass^3 of 1.0), capability cases must be no worse than the previous release beyond the standard error? That is the rule I would write in change 1's report; tell me if you want it stricter.
- 28 cases is past the 20 the playbook and Anthropic suggest as a floor. Change 2 would be too large to read as one pull request, so I would ship it as one per group of plays (1 to 3 and 9, then 4 to 7 and 10), each validated and read before the next. Do you want it that way, or one pull request?
- The workflow needs an `ANTHROPIC_API_KEY` secret and a budget for nightly runs. Real runs count against API cost: 28 cases at three trials each is 84 sessions a night. I would run the regression suite on pull requests and the capability suite weekly, not nightly. Will you set the secret, and is weekly right?
