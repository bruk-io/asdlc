# The plugin against the playbook, claim by claim

- Source: Anthropic's AI-native SDLC playbook, twelve plays in six stages (the course lessons the owner pasted, 2026-10-27). The lessons' text is not copied here; each claim below is one thing a lesson says to do or to check, in our words, with the play it comes from.
- Checked by `scripts/conformance.py`, which `./scripts/check` runs. It fails on a claim with no `built` or `tested` field, a target that does not exist, a repeated id, and a requirement R1 to R30 that serves no claim and is not listed under "Beyond the playbook".

The requirements R1 to R30 are those of [`agentic-sdlc-plugin.md`](agentic-sdlc-plugin.md); the plan for this file is [`../plan/playbook-conformance.md`](../plan/playbook-conformance.md).

## How to read a line

`- **P<play>.<n>** | the claim | requirements | built: <targets> | tested: <targets>`

- Targets are `skill:<name>`, `agent:<name>`, `command:<name>`, `hook:<file>`, `script:<file>`, `template:<file>`, `workflow:<file>`, `doc:<file>`, `file:<path from the repository root>`, `eval:<case>` and `test:<file>`. Each must exist.
- `none: <reason>` stands alone in a field and says why nothing is there. A gap written down is a finding. A gap left out would be a lie.
- `built` says what implements the claim. `tested` says what would fail if it stopped holding. A target that exists does not prove the claim holds: the evals, run for real, do that.

## Play 1. Capture as intent

- **P1.1** | An intent is written from the originator's own words, after the questions an analyst would ask: scope, users, constraints and what success looks like. | R7 | built: skill:capture-intent, command:intent | tested: eval:intent-in-their-words
- **P1.2** | The intent has a problem, a proposed outcome, affected users and systems, constraints and open questions, from one agreed template. | R7 | built: template:intent.md, script:artefacts.py | tested: test:test_artefacts.py
- **P1.3** | The originator corrects what the agent misunderstood before the intent is committed. | R7 | built: skill:capture-intent | tested: eval:intent-in-their-words
- **P1.4** | The intent is committed to a shared, version-controlled home next to the code it concerns, so author and time join the record. | R1 | built: doc:guide.md, script:asdlc | tested: eval:board-asks-where, eval:board-found-without-asking
- **P1.5** | Accepting the intent into design is a person's recorded decision. | R2 | built: script:asdlc, hook:guard_board.py | tested: test:test_guard_board.py
- **P1.6** | An intent can start from a person, a ticket or an alert, and the same steps apply. | R7 | built: skill:capture-intent | tested: none: only a person's request is evaluated; the alert route needs play 12
- **P1.7** | Time to a committed intent, and the share of intents accepted, are measured from the record. | R1 | built: script:asdlc | tested: test:test_demo_stats.py

## Play 2. Requirements and design

- **P2.1** | The accepted intent becomes a spec of numbered requirements and a design, which the product owner reviews and does not write. | R8 | built: skill:write-spec, template:spec.md | tested: test:test_artefacts.py
- **P2.2** | The spec shows how each constraint in the intent is met. | R8 | built: skill:write-spec | tested: none: no eval yet (`spec-covers-questions` is planned)
- **P2.3** | Every open question in the intent is answered or carried forward, with a reason. | R8 | built: skill:write-spec, script:artefacts.py | tested: test:test_artefacts.py
- **P2.4** | The organization's policy skills are applied while the spec is written, and the spec names the ones it applied. | R8, R11 | built: skill:write-spec | tested: none: no eval yet
- **P2.5** | Areas of concern are flagged, above all two policies that cannot both be met, each with an owner. | R8 | built: skill:write-spec | tested: none: no eval yet (`spec-flags-policy-conflict` is planned)
- **P2.6** | The product owner resolves each flagged concern with its policy owner before engineering sees the spec. | R2, R8 | built: skill:write-spec, script:asdlc | tested: none: a human step with no check
- **P2.7** | The pass is run by hand first, then codified as a command, then fired by the intent's acceptance. | R3 | built: skill:write-spec, command:intent | tested: none: nothing fires on acceptance yet
- **P2.8** | Time from intent to spec, and spec changes after the first plan, are measured. | R8 | built: script:asdlc | tested: test:test_demo_stats.py
- **P2.9** | The work is broken into tasks that each fit one repository, citing the spec's requirement numbers. | R9, R12 | built: skill:break-down-intent | tested: eval:trigger-set

## Play 3. Plan mode as the default starting point

- **P3.1** | A written plan names the files that change, the order of work and the tests that prove it, before any edit. | R9 | built: skill:plan-change, template:plan.md, command:plan | tested: test:test_artefacts.py
- **P3.2** | The plan is interrogated for what could break, the riskiest step and the options not taken, until someone who never saw the conversation could implement it. | R9 | built: skill:plan-change | tested: none: no eval yet (`plan-from-plan-alone` is planned)
- **P3.3** | The plan cites the spec's requirement numbers and flagged concerns, so a reviewer can check it line by line. | R8, R9 | built: skill:plan-change, script:artefacts.py | tested: test:test_artefacts.py
- **P3.4** | No file is edited until a person accepts the plan, and the agent cannot accept it. | R2, R9 | built: hook:guard_board.py, script:asdlc | tested: eval:approval-before-build, eval:agent-cannot-approve
- **P3.5** | The approved plan is committed with the change and joins the audit trail. | R1, R9 | built: template:plan.md | tested: test:test_artefacts.py
- **P3.6** | When the work departs from the plan, the plan is updated in the same commit. | R9 | built: skill:plan-change, file:CLAUDE.md | tested: none: no eval or hook yet (`plan-updated-on-departure` is planned)
- **P3.7** | Where a legacy tracker holds the record, one system is named the source of truth and the other links to it. | R1 | built: none: only the plugin's own board is supported | tested: none: not built
- **P3.8** | Routine work moves to auto mode as guardrails mature. | R4 | built: none: not addressed | tested: none: not built
- **P3.9** | The share of changes merging from the first pass, rework cycles per change and plan-to-diff match are measured. | R9 | built: script:asdlc | tested: test:test_demo_stats.py

## Play 4. CLAUDE.md

- **P4.1** | CLAUDE.md holds what a new joiner needs on day one (commands, conventions, architecture, what Claude gets wrong) and stays under a page. | R10 | built: script:artefacts.py, file:CLAUDE.md | tested: test:test_artefacts.py
- **P4.2** | It is checked into Git at the repository root and its changes are reviewed like code. | R10 | built: file:CLAUDE.md, workflow:review.yml | tested: test:test_workflows.py
- **P4.3** | A mistake made twice gets a line in it. | R10 | built: agent:reviewer | tested: eval:repeat-mistake-claude-line
- **P4.4** | Review flags a change that has made CLAUDE.md out of date. | R10, R15 | built: file:REVIEW.md | tested: none: no eval yet
- **P4.5** | `/init` and the onboarding skill start a repository's file and its commands. | R10 | built: skill:onboard-repo | tested: none: no eval yet (`onboard-runs-what-it-writes` is planned)
- **P4.6** | How often Claude repeats a mistake the file should have caught is tracked in the history. | R10 | built: none: not measured | tested: none: not built

## Play 5. Skills as institutional knowledge

- **P5.1** | A skill holds one policy with a named owner and a written source of truth. | R11 | built: skill:write-policy-skill, template:policy-skill.md | tested: eval:policy-skill-names-the-real-backstop
- **P5.2** | Its frontmatter says when it triggers, and it loads when the task is asked for in different ways. | R11 | built: skill:write-policy-skill | tested: eval:trigger-set
- **P5.3** | Skills ship in the repository or through a plugin, and the policy owner signs off a change to one. | R11 | built: doc:repo-plugins.md | tested: none: sign-off is a human step
- **P5.4** | A policy that must always hold is backed by a hook at the edit and the same check as a required pull request check. | R11 | built: skill:write-policy-skill | tested: eval:policy-skill-backed-by-hook-and-ci, eval:policy-skill-flags-an-enforcement-gap
- **P5.5** | Knowledge that needs no consistency stays out of skills and in CLAUDE.md or a prompt; a preference stays advisory. | R11 | built: skill:write-policy-skill | tested: eval:policy-skill-preference-advisory
- **P5.6** | Build-time hooks block edits to protected paths and are fast and scoped to the file that changed. | R13, R16 | built: hook:guard_test_edits.py, hook:guard_board.py | tested: test:test_hooks.py, test:test_guard_board.py
- **P5.7** | A formatter and linter run after edits, and credentials stay out of the diff. | R13 | built: none: no hook does either | tested: none: not built
- **P5.8** | Heavier checks run at the commit or the pull request, not on every edit. | R13 | built: workflow:ci.yml, script:check | tested: test:test_workflows.py
- **P5.9** | Pull request findings that cite a policy are tracked, and should fall toward zero. | R11 | built: none: not measured | tested: none: not built

## Play 6. Parallel sessions and subagents

- **P6.1** | Each parallel task runs in its own worktree, and tasks that share files run one after another. | R12 | built: skill:orchestrate, script:asdlc | tested: test:test_demo_orchestration.py
- **P6.2** | Repeated jobs are subagents defined in the repository with a name, a description and scoped tools, and a verifier reports without fixing. | R12 | built: agent:worker, agent:reviewer | tested: none: no trace check that the reviewer has no edit tools
- **P6.3** | Start with two or three sessions; the ceiling is how many streams one person can review properly. | R12 | built: skill:orchestrate | tested: none: not enforced or measured
- **P6.4** | Permissions are tuned so sessions do not wait on prompts for commands the organization considers safe. | R12 | built: script:asdlc | tested: test:test_asdlc.py
- **P6.5** | Concurrent sessions per engineer, and changes merged beside rework, are measured. | R12 | built: none: not measured | tested: none: not built

## Play 7. A feedback loop

- **P7.1** | Each check tier is one command that exits non-zero on failure, with its healthy output known. | R13 | built: script:check | tested: test:test_check.py
- **P7.2** | A bug is reproduced as a committed failing test before it is fixed. | R13 | built: none: no skill, agent or hook says so | tested: eval:bug-repro-first
- **P7.3** | The fix cannot edit the test, enforced by a hook. | R13 | built: hook:guard_test_edits.py | tested: eval:fix-cannot-edit-tests, test:test_hooks.py
- **P7.4** | The agent runs the checks and shows their output before reporting done. | R13 | built: agent:worker | tested: eval:claims-backed-by-output
- **P7.5** | UI work closes the loop with a visual check against the mock. | R13 | built: none: no browser or screenshot tooling | tested: none: not built
- **P7.6** | First-pass CI success and review time per pull request are measured. | R13 | built: script:asdlc | tested: test:test_demo_stats.py

## Play 8. Continuous evals in CI

- **P8.1** | A suite of 20 to 50 real tasks, each a prompt plus the checks that define acceptable. | R14, R28 | built: script:eval | tested: test:test_eval.py
- **P8.2** | The suite runs non-interactively on any change to CLAUDE.md, skills or hooks. | R14 | built: script:eval, script:gate_evidence.py | tested: test:test_gate_evidence.py
- **P8.3** | The suite also runs on a schedule, in CI. | R14 | built: workflow:ci.yml | tested: none: CI runs only `validate`; no scheduled or path-triggered real run, and the gate has never been run for real
- **P8.4** | The checks stay out of the run's checkout, and grading happens from a copy. | R14 | built: script:eval | tested: test:test_eval.py
- **P8.5** | The configuration under test is copied in whole, and `--bare` is never used. | R14 | built: script:eval | tested: test:test_eval.py
- **P8.6** | A configuration change that drops the pass rate is reviewed before it merges. | R22 | built: script:gate_evidence.py, hook:guard_gate.py | tested: test:test_guard_gate.py, test:test_gate_evidence.py
- **P8.7** | The suite stays live: cases that stop discriminating are retired and new ones come from monitoring. | R24 | built: script:eval | tested: test:test_eval.py
- **P8.8** | Every incident leaves an eval behind, and the time from incident to eval is tracked. | R24 | built: none: no incident intake | tested: none: not built
- **P8.9** | The pass rate over time is reported on every run. | R29 | built: script:eval | tested: test:test_eval.py

## Play 9. AI in the PR review loop

- **P9.1** | Every pull request gets the same review passes (bugs, security, compliance against the spec and the plan, design), each finding tagged with its pass. | R15 | built: agent:reviewer, file:REVIEW.md, workflow:review.yml | tested: eval:reviewer-recall, eval:reviewer-full-verdict
- **P9.2** | The review policy defines Important against Nit, caps the nits and lists what to skip. | R15 | built: file:REVIEW.md | tested: eval:reviewer-false-alarm
- **P9.3** | Findings never approve or block on their own, and the agent that wrote a change cannot approve it. | R2, R15 | built: hook:guard_board.py, workflow:review.yml | tested: test:test_guard_board.py, test:test_workflows.py
- **P9.4** | The compliance pass reads the committed spec and plan and finds what the diff alone would not show. | R15 | built: agent:reviewer | tested: none: no eval yet (`reviewer-checks-against-plan` is planned)
- **P9.5** | A reviewer's `@claude` comment makes the agent address it and push the fix. | R15 | built: workflow:claude.yml | tested: test:test_workflows.py
- **P9.6** | A mistake a review flags twice goes into CLAUDE.md as part of that review. | R10, R15 | built: agent:reviewer | tested: none: no eval yet
- **P9.7** | The findings are rated and the nits capped monthly so the reviewer improves. | R15 | built: none: no rating loop | tested: none: not built

## Play 10. Hooks as approval gates

- **P10.1** | Each required approval is a hook that allows, asks or blocks, and the agent cannot pass it. | R16 | built: hook:guard_board.py, hook:guard_gate.py | tested: eval:agent-cannot-approve, test:test_guard_board.py, test:test_guard_gate.py
- **P10.2** | A block shows the reason and the route to approval in the agent's output. | R16 | built: hook:guard_board.py, hook:guard_gate.py | tested: test:test_guard_board.py
- **P10.3** | Every hook decision is logged with a timestamp. | R26 | built: hook:decision_log.py | tested: test:test_hooks.py
- **P10.4** | Non-negotiable hooks live in managed settings that individual engineers cannot switch off. | R17 | built: none: no managed-settings template | tested: none: not built
- **P10.5** | The records a gate reads are ones the agent has no way to write. | R2, R16 | built: hook:guard_board.py, hook:guard_gate.py | tested: eval:agent-cannot-approve

## Play 11. CI/CD integration and deployment

- **P11.1** | Agent jobs in CI start read-only, and write steps arrive as pull requests with no route to the default branch. | R18 | built: workflow:review.yml, workflow:claude.yml | tested: test:test_workflows.py
- **P11.2** | Agent jobs run sandboxed with short-lived scoped tokens and no standing production credentials. | R18 | built: workflow:review.yml | tested: test:test_workflows.py
- **P11.3** | Deploy, status and rollback are scoped tools per environment, with the autonomy tiered by environment. | R18 | built: none: no deployment tooling | tested: none: not built
- **P11.4** | The agent prepares a release and a person authorizes the production one, enforced by a hook. | R18 | built: none: no release skill | tested: none: not built
- **P11.5** | Rollback is one command, rehearsed regularly in staging. | R18 | built: none: no rollback path | tested: none: not built
- **P11.6** | Pipeline failures triaged without paging a human, and the DORA measures, are tracked. | R18 | built: none: not measured | tested: none: not built

## Play 12. Closing the loop on metrics

- **P12.1** | A deterministic, version-controlled script watches a metric against control bands and detects drift as well as spikes. | R19 | built: none: no detector | tested: none: not built
- **P12.2** | The response is tiered: log at 1σ, diagnose read-only at 2σ, open a pull request or run a pre-approved runbook at 3σ. | R19 | built: none: no tiers | tested: none: not built
- **P12.3** | A breach is written as an intent with the anomaly, its evidence and any action already taken. | R7, R19 | built: skill:capture-intent | tested: none: no eval yet (`incident-becomes-intent` is planned)
- **P12.4** | When a fix ships, the incident leaves an eval behind. | R24 | built: none: no incident intake | tested: none: not built
- **P12.5** | An independent gate, a deterministic check or an adversarial reviewing agent, sits between stages of a headless run. | R19 | built: none: nothing runs headless | tested: none: not built
- **P12.6** | The owner triages findings, and dismissals tune the bands. | R19 | built: none: no triage queue | tested: none: not built

## Beyond the playbook

Requirements that serve no claim above. Each is something this plugin does that the lessons do not ask for.

- R5: gate owners are configured per repository. The lessons name an approver for each gate; configuring who it is per repository is ours.
- R6: a stand-in eval runs and is visible at a gate whose owner also did the work. The lessons assume a separate person.
- R20: every change to the plugin starts as an intent in this repository. The plugin building itself is ours.
- R21: the released version builds the next one in a worktree and never edits the copy it runs from. Ours.
- R23: the eval suite sits under a protected path, and a change to the plugin cannot also change the suite. The lessons grade from a copy kept out of the run; protecting the suite from the change under test goes further.
- R25: the suite reruns with each component removed in turn, and a component whose removal costs nothing becomes an intent to delete it. Ours.
- R27: a script builds a session index from the transcripts. The lessons use an OpenTelemetry export; this is our version of it.
- R30: a quarter of the cases form a private holdout that only CI reads. Ours.
