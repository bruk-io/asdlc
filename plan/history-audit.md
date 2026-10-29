# Plan: an audit of the repository's own history against its own rules

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md)
- Status: approved by the owner in session, 2026-10-29. Built; see Departures and What it found.
- Delivers: R20 (every change to the plugin starts as an intent and goes through the loop), with R9 (plan approved before edits), R23 (suite and plugin never change together) and R1 (each stage leaves a committed artefact) as the rules it reads.

The repository says it builds itself: every change carries an approved plan, and a pull request that changes the plugin never changes the suite. Nothing checks that this was done, only that each new pull request passes today's checks. This change reads the 37 merged pull requests (and any branch before it merges) and reports, rule by rule, where the history departs from the rules. It is the second step of `plan/playbook-conformance.md`'s series and the first thing that tests adherence, not just the mapping.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/history_audit.py` | yes | `audit(pulls)` and `indicators(pulls)` take data and return data; the shell reads `git log --first-parent` for each merge commit, then the commits and files between its parents. A `--report` prints the findings and a table of indicators; the exit code is 1 on an unwaived finding. An optional `--pulls <json>` adds facts git does not hold (checks at merge, who merged), exported from the GitHub API | R20 |
| `scripts/history_waivers.toml` | yes | Known departures, each by pull request number and rule, with the reason and who accepted it. The audit counts a waived finding and lists it; it never hides one | R20 |
| `tests/test_history_audit.py` | yes | A small made-up history for each rule, one that breaks it and one that does not, plus the waiver and the report | R20 |
| `docs/guide.md` | no | A paragraph: what the audit reads, how to run it, how to waive | - |
| `CHANGELOG.md` | no | One line | - |
| `plan/history-audit.md` | yes | This plan | R20 |

## The rules it reads

Each is a finding, with the pull request and the reason the rule exists.

1. **H1, a plan travels with the change (R20).** A pull request that changes the plugin (anything under `skills/`, `commands/`, `hooks/`, `agents/`, `scripts/`, `templates/` or `.github/workflows/`) adds or edits a file under `plan/`.
2. **H2, the plan comes first (R9).** In the pull request's commits, oldest first, the first commit touching `plan/` is no later than the first commit touching the plugin. Same commit counts.
3. **H3, an approved plan ships with code (R9).** When a pull request changes the plugin, the plan's `Status:` line at the merge is not `draft`. A plan-only pull request is exempt: merging it is the approval.
4. **H4, suite and plugin never together (R23).** No pull request changes both `evals/` (or `spec/*-evals.md`) and the plugin.
5. **H5, tests ship with scripts and hooks.** A pull request that changes a script or hook changes something under `tests/` (the repository's own convention in `CLAUDE.md`).
6. **H6, the change is announced.** A pull request that changes the plugin changes `CHANGELOG.md`, from the first pull request that had one.
7. **With `--pulls` only:** H7, the required checks (`check`, `protected-paths`) passed at merge.

The playbook's own lagging indicators are reported beside the findings, not judged: plan-to-diff match (the share of changed plugin files the plan names), plan commits after the first code commit (rework), commits and lead time from first commit to merge, and the share of pull requests that merged from their first implementation commit.

## Departures

- **H8 is dropped.** The plan had a rule that a person made the merge. Every merge here goes through the owner's own token, whether the owner or this agent pressed it, so GitHub cannot tell them apart and the rule would say nothing.
- **H2 and H3 apply to a plan the pull request adds.** Reading the first findings by hand showed they fired on plans already on `main`: a plan merged in a plan-only pull request was approved by that merge, and a later build pull request that edits it is not a draft or a late plan. This is the step-2 rule fix the plan promised, not a waiver.
- **The pull request count is 31, not 37.** Only merge commits on the first-parent line are pull requests; the rest of the numbers were never merged.
- **`--ref` and `--range`.** The command reads any ref, and `--range base..head` audits a branch as if it were one pull request. It refuses a shallow clone, since the parents are missing.

## Order of work

1. Write the pure functions and the tests for H1 to H6 against made-up histories.
2. Write the shell and run it on this repository. Read every finding by hand: a rule that fires on a legitimate pull request is a bug in the rule, fixed in the rule and not waived.
3. Export the merged pull requests' check runs and merger through the GitHub API, add H7 and H8, and run again.
4. Record each real departure in `scripts/history_waivers.toml` with the reason, only with the owner's say-so, or leave it as a finding. Write the guide paragraph and the changelog line.
5. Run `./scripts/check` and paste the result, and put the audit's report in the pull request.

## Questions for the owner

- **How far back?** The rules are dated 2026-10-20 (the spec) but the first ten pull requests built the loop itself. I propose to report everything and to judge from PR #4 (`v0-bootstrap`) on; earlier ones are listed as informational.
- **Is this a report or a gate?** I propose a report you run on demand, plus one run before each merge on the branch alone (`--range origin/main..HEAD`), not added to `./scripts/check` yet. Making it a required check is a separate decision once its findings are trusted.
- **Waivers.** The stacked-pull-request exception (the suite and the plugin changing in two pull requests that merged in order) is not a departure, but "short circuit the rules for now" on the skill split in PR #32 is. I would list it and ask you before waiving.

## What it found

On `main` at the merge of #37: 31 pull requests, 11 findings judged, none waived, all 7 rules run (H7 on the 19 pull requests that had check runs; all required checks were green. PR #10's `review` job failed and it merged: `review` is not a required check and #10 fixed that workflow).

- **H1, no plan (#11, #12):** two GitHub Actions workflow pull requests, one an installer's, one a fix, with no plan.
- **H3, a new plan still `draft` when its code merged (#16, #22 four plans, #33, #35):** the approval happened in the session and the plan file was not updated to say so. #35 is this agent's own: `plan/remove-multi-machine.md` still says draft after the owner's "approved".
- **H2 and H6, the skill split (#32):** the code came before the plan and no changelog line, the one the owner said to short-circuit. Left as an open finding.

## Risks

- **Git is a proxy.** A plan file edited in a pull request is not proof that a person approved it, and a missing file is not proof that nobody did. The audit says what the history shows and that it cannot see the in-session approval. Medium.
- **A rule that fires on legitimate work.** Plan-only and doc-only pull requests, merges of `main` into a branch, and the custom merge message formats on PRs #22 to #27 would all confuse a naive reader. Step 2 reads every finding to catch this before anyone trusts the report. Medium.
- **Waivers become the way to pass.** A waiver needs a reason and a name, is listed in every report, and is a diff the reviewer sees. Low to medium.
- **Reading merge commits misses a squash.** Every merge so far is a merge commit; the audit reports any first-parent commit it cannot read as a pull request. Low.

## Proof

- `./scripts/check` passes, its output pasted in the pull request.
- The tests show each rule firing on a bad history and staying quiet on a good one.
- The pull request carries the audit's report on this repository: the findings by rule, the waivers, and the indicators for the 37 merged pull requests, with the findings I read by hand and judged real or not.
