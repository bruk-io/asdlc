---
kind: task
step: 1
delivers: [R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15]
size: 5
---
# Task: the generating-a-plan skill and its three cases

## What to build

Step 1 of the plan, in one pull request, on top of the spec skill's two tasks.

- `plugins/asdlc/skills/generating-a-plan/SKILL.md`: a description that says when it loads, and the seven steps of the spec's design as its body. It works in an ordinary session, and a step that waits on a question the spec carried names its concern and decides nothing.
- Three cases under `plugins/asdlc/evals/`, each a `case.yaml` and a `scaffold.sh` that builds its repository with plain git: `plan-from-an-accepted-spec`, `plan-with-a-carried-question` and `plan-waits-for-the-merge`.
- `README.md` gains the skill.

The plan's step 1 says what each case's repository holds and what its patterns and its judge check.

## Done when

- `just check` passes, with the shape check reading three skills and eight cases, and every scaffold's documents linted.
- `just eval --tag generating-a-plan` runs the three cases three times each, and its report is in the pull request.
- In the acting cases, patterns that open `plan.md` by path show every requirement on a `- delivers:` line and under "Proof", the spec's concern under "Risks", the scaffold's module listed with no "(new)", and no placeholder left.
- In the case that stays out, no `plan.md` exists, no `plan/` branch was made by hand, and nothing was merged.
- R11 is shown in a live session on a copy of the repository, and the pull request says how that went and that R12 was not shown.
