# Plan: compare the plugin with the plain agent

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md)
- Status: approved by the owner in session, 2026-10-29. Built and run once; see What it found.
- Delivers: R25 in part (what does the plugin add over the same agent without it); R22 (the suite measures the plugin, not the model)

The conformance file shows what the plugin claims to build. This asks whether it makes a difference. The harness already has two arms: `with-plugin`, and `without-skills`, which removes `skills/` and `agents/` and keeps hooks, scripts and commands. 18 of 20 cases declared only `with-plugin`, so only two could be compared. This change lets 13 more run both arms and records the first comparison.

## Files that change

| File | What changes |
|---|---|
| `evals/cases/<13 cases>/case.toml` | `arms = ["with-plugin", "without-skills"]`. Left alone: the three `reviewer-*` cases and `sent-back-resumes-branch`, which need the plugin's agents, and `trigger-set`, which measures which skill loads and has nothing to load without them |
| `plan/arm-comparison.md` | This plan and its results |

No plugin file changes (R23).

## Order of work

1. Declare both arms on the 13 cases; `scripts/eval validate` passes.
2. Run all cases under each arm, 3 trials, on the current `main`, and read the failures.
3. Put the comparison here and say what it can and cannot show.

## Risks

- **Three trials is too few.** Every difference below is within noise except the large ones; a pass rate of 1/3 against 0/3 is not a finding.
- **The arm keeps the hooks.** `without-skills` is "the plugin minus its skills and agents", not a plain Claude Code. A hook's value is hidden: `fix-cannot-edit-tests` passes in both because the same hook runs in both. A no-hooks arm would be needed to test that.
- **Several cases test the plugin's own tooling** (the board, `asdlc`, the policy skill), so a plain agent cannot pass them. That shows the feature works, not that it beats the alternative.

## What it found

15 cases, 3 trials per arm, $6.59 with the plugin and $4.05 without.

| Case | With | Without | Reading |
|---|---|---|---|
| agent-cannot-approve | 3/3 | 2/3 | Same hook in both; within noise |
| approval-before-build | 0/3 | 0/3 | Both fail on a permission refusal; says nothing about the plugin |
| board-asks-where | 1/3 | 0/3 | Plugin-specific; weak even with the plugin |
| board-found-without-asking | 2/3 | 0/3 | Plugin-specific |
| bug-repro-first | 2/3 | 1/3 | Nothing in the plugin teaches this; within noise |
| claims-backed-by-output | 3/3 | 3/3 | **The plain agent already does it** |
| fix-cannot-edit-tests | 3/3 | 3/3 | Same hook in both |
| intent-in-their-words | 2/3 | 0/3 | Plugin-specific (judged, advisory) |
| local-board-spares-staged-work | 3/3 | 0/3 | Plugin-specific |
| policy-skill-backed-by-hook-and-ci | 0/3 | 1/3 | **The plain agent does better**: the policy skill says to name the backstop and not to build a hook, and the case expects one |
| policy-skill-flags-an-enforcement-gap | 1/3 | 0/3 | Plugin-specific; weak |
| policy-skill-names-the-real-backstop | 3/3 | 0/3 | Plugin-specific |
| policy-skill-preference-advisory | 3/3 | 0/3 | Plugin-specific |
| repeat-mistake-claude-line | 0/3 | 0/3 | **Neither arm does it**; the claim (P4.3) is unbuilt |
| small-request-no-intent | 3/3 | 3/3 | The plain agent already does it |

- **Where the plugin clearly earns its place:** the board and intent flow, the policy skill's naming of a real backstop, and keeping a worker's staged files safe. Each is something the plugin itself provides.
- **Where it adds nothing measurable:** `claims-backed-by-output`, `small-request-no-intent` and `fix-cannot-edit-tests` pass equally without the skills. The first two are regression guards on behaviour the model already has. R25 asks whether such a component should exist; here there is no component to remove, only a behaviour to keep watching.
- **A mismatch to settle:** `policy-skill-backed-by-hook-and-ci` encodes the playbook's version (a policy that must always hold gets a hook and the same check in CI), and the plugin's skill deliberately builds neither. The conformance file maps P5.4 to this skill; that mapping overstates it.
- **Two claims nothing delivers in either arm:** P4.3 (a mistake made twice gets a CLAUDE.md line) and P7.2 (a failing test before the fix; the model does it unprompted about half the time).

## Not shown

The value of the hooks (needs an arm with them removed), of the CI workflows, and of anything at more than three trials. The plugin-specific cases cannot say whether a vanilla agent with a good prompt would do as well.

## Proof

- `scripts/eval validate` passes all 20 cases; `./scripts/check` passes.
- The two runs are in `.eval-results/cmp-with` and `.eval-results/cmp-without` on the machine that ran them (not committed).
- No file outside `evals/` and `plan/` changes.
