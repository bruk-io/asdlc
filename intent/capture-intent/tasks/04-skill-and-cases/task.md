---
kind: task
step: 4
delivers: [R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R13, R15, R16]
depends: [02-session-install, 03-eval-shape]
size: 5
---
# Task: the capturing-intent skill, its two cases, and just eval

## What to build

Step 4 of the plan, in one pull request.

- `plugins/asdlc/skills/capturing-intent/SKILL.md`: a description that says when it loads, and the six steps of the spec's design as its body.
- `plugins/asdlc/evals/intent-in-their-words/` and `plugins/asdlc/evals/small-request-no-intent/`, each with `case.yaml` and a `scaffold.sh` that makes the run's folder a git repository with a `main`, one commit and a `user.name`.
- A `just eval` recipe, and `plugins/asdlc/evals/results/` in `.gitignore`.
- `CLAUDE.md` and `README.md` gain the skill, the cases and `just eval`.

The plan's step 4 says what each case's prompt holds and what its patterns and its judge check.

## Done when

- `just check` passes, which now includes the shape check over a real skill and its two cases.
- `just eval` runs both cases three times each, and its report is in the pull request.
- In the acting case, patterns show the skill loaded, `asdlc intent new` ran, the draft holds both planted facts and a `### Q1:`, and nothing was pushed.
- In the case that stays out, patterns show the fix was made and nothing under `intent/` was created.
- R7 and R8 are shown by capturing this repository's next intent with the skill in a live session, and the pull request says how that went.
