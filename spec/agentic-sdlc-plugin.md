# Spec: an agentic SDLC plugin that builds itself

- Intent: [`intent/agentic-sdlc-plugin.md`](../intent/agentic-sdlc-plugin.md), accepted 2026-10-20 (#1)
- Status: draft. Merging this file approves it and starts planning.
- Evals: [`agentic-sdlc-plugin-evals.md`](agentic-sdlc-plugin-evals.md) is part of this spec.

The plugin implements all twelve plays of Anthropic's AI-native SDLC playbook as one Claude Code plugin, keeps every artefact as a plain file in git with a pull request as each gate, and replaces itself only when its own eval suite says the new version is no worse. The four design choices that answer the intent's open questions were agreed by the gate owner on 2026-10-20.

## Requirements

### The loop

- **R1.** Each stage ends in a committed artefact that the next stage reads: intent (Plan), spec (Design), plan (Build), the change with its check evidence (Test), the reviewed pull request (Deploy), the incident record (Maintain).
- **R2.** Each gate is passed by a recorded human action, and git records who passed it and when.
- **R3.** Each gate can be run by hand as a command before it is automated. Once automated, an accepted artefact starts the next stage: an accepted intent starts the spec pass, an approved spec starts planning, a merged change starts the pipeline, and a breached band writes an intent.
- **R4.** Each play can be enabled on its own once its prerequisites, as the playbook's dependency graph gives them, are in place.

### Team size

- **R5.** Gate owners are configured per repository. One person may own every gate.
- **R6.** When the owner of a gate also did the work it judges, that gate's stand-in eval (evals file, "Stand-ins") must run and be visible at the gate.

### The plays

- **R7. Capture intent.** An intent has a problem, a proposed outcome, affected users and systems, constraints and open questions, written from the requester's words after analyst-style questions.
- **R8. Requirements and design.** A spec has numbered requirements, a design, areas of concern, and every open question from its intent answered or carried forward with a reason. It applies the repository's policy skills while it is written.
- **R9. Plan.** A plan names the files that change, the order of work, the risks and the proof, and is approved before any file is edited. A change that departs from its plan updates the plan in the same commit.
- **R10. CLAUDE.md.** It stays under a page. A mistake made twice gets a line in it.
- **R11. Skills.** A skill holds one policy with a named owner and source. A policy that must always hold is also enforced by a hook or a check.
- **R12. Parallel sessions and subagents.** Each parallel task runs in its own worktree; tasks that share files run in sequence. Recurring jobs are subagent definitions in the repository.
- **R13. Feedback loop.** Each check tier is one command that exits non-zero on failure. A bug is reproduced as a committed failing test before it is fixed, and test files cannot be edited while fixing it.
- **R14. Continuous evals.** The eval suite runs on every change to the plugin's configuration (CLAUDE.md, skills, hooks, agents, commands) and on a schedule.
- **R15. PR review.** Every change gets the review passes a `REVIEW.md` defines, findings ranked by severity. The agent that wrote a change cannot approve it.
- **R16. Approval hooks.** Each required approval is a hook that blocks with the reason and the route to approval, and every hook decision is logged.
- **R17. Managed settings.** The plugin ships a managed-settings template covering permissions, sandboxing and hooks that must not be switched off.
- **R18. CI/CD.** Agent jobs in CI start read-only; write steps arrive as pull requests; release and rollback are scoped commands; an agent may prepare a release but not publish it.
- **R19. Closing the loop.** Detection is a deterministic script over metrics, with bands in versioned config: log at 1σ, diagnose read-only at 2σ, open a pull request or run a pre-approved runbook at 3σ. Every diagnosis is written as an intent.

### Self-building

- **R20.** Every change to the plugin starts as an intent in this repository and goes through the loop.
- **R21.** The released version builds the next one in a worktree. It never edits the copy it is running from.
- **R22.** A change to the plugin merges only if the eval suite scores it no worse than the current release, beyond the measured run-to-run spread.
- **R23.** The eval suite sits under a protected path. A pull request that changes the plugin cannot also change the suite, enforced in CI.
- **R24.** New eval cases come only from incidents or from a person.
- **R25.** On a schedule and after every model change, the suite reruns with each component removed in turn. A component whose removal costs nothing becomes an intent to delete it.

### Measurement

- **R26.** Every hook appends one JSON line per decision: time, hook, tool, verdict, reason, artefact id.
- **R27.** A script builds a session index from Claude Code session transcripts: artefact id, skills loaded, subagents spawned, tool calls, tokens, prompts shown to a person.
- **R28.** Every eval in the evals file is implemented, using deterministic checks first and a model judge only where none exists.
- **R29.** Every eval run records its cost: input and output tokens per case and in total, wall time, the model, and the cost at published API prices, even when the run uses a subscription.
- **R30.** About a quarter of the eval cases form a private holdout set that only CI can read. A change merges only when both the public suite and the holdout hold, and the holdout is reported as an aggregate score, never as cases.

## Design

### Shape of the plugin

| Part | What it holds |
|---|---|
| Skills | One per play, carrying the judgement that play needs |
| Commands | One per gate, so each stage can be run by hand (R3) |
| Hooks | Guards for must-hold policies, approval gates, the decision log |
| Agents | Reviewer (read-only, cannot approve its author's work), verifier |
| Scripts | Every deterministic check: artefact shape, coverage, plan drift, detection, metrics |
| CI workflows | Evals, review, release, detection; templates for repositories that install the plugin |
| Templates | Intent, spec, plan, `REVIEW.md`, bands, managed settings |

### Where artefacts live (answers intent question 1) - agreed

Plain files in git, as the playbook has them, with a pull request as the gate for each:

| Artefact | Path | Gate |
|---|---|---|
| Intent | `intent/<slug>.md` | Merge of its pull request |
| Spec | `spec/<slug>.md` | Merge of its pull request |
| Plan | `plan/<slug>.md` | Merge before implementation starts |
| Change | The pull request and its check runs | Review, then merge |
| Incident | `incident/<date>-<slug>.md` | Triage: fix, schedule or dismiss |

Why: no tracker dependency, git is the single timestamp authority, every eval can read history directly, and the playbook's legacy-systems sidebar covers linking to a tracker if a repository has one.

### Where the first eval cases come from (answers intent question 2) - agreed

Version 0 is built by hand and contains only the playbook's no-prerequisite plays: capture intent, CLAUDE.md, skills, feedback loop, hooks, plan mode. From then on the plugin's own history supplies cases. Until it holds 20, the maintainer writes a case by hand for each play as it lands, and the gate in R22 compares against those.

### Infrastructure plays without an organisation (answers intent question 3) - agreed

The plugin's own release is its production:

- **Deploy** is publishing a version: a tag and a marketplace entry.
- **Rollback** is pointing the marketplace entry back at the previous tag.
- **Production metrics** are the plugin's own outcome metrics (evals file).
- **Managed settings** are applied on the maintainer's machine from the template.

### Model judges (answers intent question 4) - agreed, partly carried forward

No judge until an eval has no deterministic check. The first judge is introduced with a labelling step in review, where the gate owner rates a sample of its verdicts; it gates nothing until it agrees with those labels. How many labels are enough is carried forward until the first judge exists.

### Private holdout set - agreed

- The holdout lives in a private repository (`bruk-io/asdlc-holdout`).
- The public repository's eval workflow fetches it with a read-only deploy key stored as a CI secret. Building sessions are never given that repository.
- CI publishes the holdout's aggregate score, cost and run-to-run spread beside the public suite's, and never a case, transcript or diff from it.
- A widening gap between the public and holdout scores is read as the plugin fitting its public cases, and becomes an intent.
- Holdout cases are drawn the same way as public ones (R24) and assigned at random when they are added.

The plugin, its evals and how it is judged stay public; only the answer key is private, so this keeps to the intent's public-repository constraint.

### Language for scripts and hooks

Carried forward to planning: the choice depends on what runs with no install step wherever the plugin is installed.

## Areas of concern

- **One person at every gate.** The stand-ins in R6 reduce self-approval but do not remove it. The gate owner accepted that residual risk on 2026-10-20: self-approval is allowed, and the stand-ins stay visible at each gate.
- **The loop judging itself.** A hook can be bypassed locally, so R23's protection has to live in CI, where the plugin under test cannot reach it.
- **Public eval cases.** The agent building the plugin can read the public cases and tune the plugin to them, and public cases may end up in future training data. The private holdout set (R30) answers both; its residual risk is that a case leaks through a log or a failure message, so CI output from holdout runs is reduced to scores before it is published.
- **Eval cost.** Runs use a subscription, so cost shows up as usage limits rather than a bill. R29 records it anyway; the cadence in R14 and R25 is set once one full run is measured.

## Out of scope

Nothing in the playbook. Anything not named in the requirements is out of scope until an intent brings it in.
