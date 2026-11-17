---
kind: plan
---
# Plan: a skill that generates a plan

## Files that change

- plugins/asdlc/skills/generating-a-plan/SKILL.md (new)
- plugins/asdlc/evals/plan-from-an-accepted-spec/case.yaml (new)
- plugins/asdlc/evals/plan-from-an-accepted-spec/scaffold.sh (new)
- plugins/asdlc/evals/plan-with-a-carried-question/case.yaml (new)
- plugins/asdlc/evals/plan-with-a-carried-question/scaffold.sh (new)
- plugins/asdlc/evals/plan-waits-for-the-merge/case.yaml (new)
- plugins/asdlc/evals/plan-waits-for-the-merge/scaffold.sh (new)
- README.md

## Order of work

This is built on top of the spec skill's two tasks. It needs nothing new from the package: `asdlc plan new` already refuses a spec that is not on `main`, and lint already has the `delivers`, `coverage` and `files` rules.

### Step 1: The skill and its three cases
- delivers: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15

One step, because `just check` fails on a skill that lands without both kinds of case.

**The skill.** `plugins/asdlc/skills/generating-a-plan/SKILL.md`. Its description says when it loads: someone asks for the plan of an intent, or how an accepted spec will be built (R1). Its body is the seven steps of the spec's design, in that order, and it reads like `plugins/asdlc/skills/generating-a-spec/SKILL.md` so the three skills work alike. It follows what the spec's C1 and C2 propose, which their owner has not yet decided:

- It works in an ordinary session, not in plan mode.
- A step that depends on a question the spec carried keeps its `- delivers:` line, names the concern it waits on, and decides nothing (R10).

**The cases.** Each `scaffold.sh` builds its repository with plain git and writes its documents out in full, as the spec skill's scaffolds do. The intent's slug is `claim-steps` in all three, so graders open `intent/claim-steps/plan.md` by its path. Each prompt asks for the plan of that intent and says nothing else.

- `plan-from-an-accepted-spec`, tagged `generating-a-plan` and `acts`. `main` holds the intent and its spec, with three requirements and one area of concern the work runs into, and the two modules the spec's design names. Patterns check that:
  - `asdlc plan new` ran, and `plan.md` is the only file created (R2, R13);
  - `claims_gateway.py` is listed with no "(new)" after it, and no path is listed without "(new)" other than the files the scaffold made (R4);
  - each of R1, R2 and R3 is on a `- delivers:` line (R5, R6) and named under "Proof" (R8);
  - "Risks" names `C1` (R7);
  - no placeholder from the template is left (R14), and nothing was pushed (R11).

  A judge checks that each step says what changes and in which files (R9).
- `plan-with-a-carried-question`, tagged `generating-a-plan` and `acts`. The spec carried one question to `C1`, and its `R2` cannot be built until that is answered. Patterns check that "Risks" names `C1`, and that the step delivering `R2` names `C1` too (R7, R10). A judge checks that the plan does not decide the question (R10).
- `plan-waits-for-the-merge`, tagged `generating-a-plan` and `stays-out`. The spec is on the branch `spec/claim-steps` and not on `main`. Patterns check that no `plan.md` was created, that no `plan/` branch was made by hand, that Claude merged nothing, and that the answer says the spec has to be merged first (R3).

`tests/test_evals.py` does not change. It already finds every skill and case, and lints what each scaffold builds. `README.md` gains the skill in its table.

## Risks

- **The skill is built on two proposals nobody has accepted.** C1 and C2 in the spec are carried with their owner. If either is decided the other way, the skill's steps 1 and 4 change, and `plan-with-a-carried-question` changes with them.
- **A run is one turn.** A skill that asks before writing produces no plan. The scaffolded specs leave nothing to ask.
- **The pattern for R4 knows the scaffold's files by name.** It shows the skill listed no file that is not there, in a repository of four files. It says nothing about a large one (C5).
- **R9 rests on a judge** (C4), and so does the half of R5 about a step that delivers nothing.
- **The suite grows to eight cases.** With three runs each, with and without the plugin, that is 48 runs. `just eval --tag generating-a-plan` runs this skill's three.

## Proof

- **`just check`.** The shape check reads the new skill and its cases, and the scaffold test lints the three new repositories.
- **R1 to R10, R13, R14, R15.** `just eval --tag generating-a-plan`, three runs a case, with its report in the pull request.
- **R11.** A live session on a copy of the repository where this intent's own plan is taken out and the merges below are simulated: the skill writes the plan again, shows the draft, and applies one correction. This plan was written by hand, because the skill did not exist yet.
- **R12.** Not shown, for the reason the spec skill's was not: in that copy there is no remote to push to. The skill opening a pull request is seen the first time it is used after the stack is merged.
