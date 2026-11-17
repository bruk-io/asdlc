---
kind: task
step: 2
delivers: [R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16]
depends: [01-repeated-property]
size: 5
---
# Task: the generating-a-spec skill and its three cases

## What to build

Step 2 of the plan, in one pull request, on top of capture-intent's four tasks and of task 01.

- `plugins/asdlc/skills/generating-a-spec/SKILL.md`: a description that says when it loads, and the seven steps of the spec's design as its body, with the three rules the plan spells out.
- Three cases under `plugins/asdlc/evals/`, each a `case.yaml` and a `scaffold.sh` that builds its repository with plain git: `spec-from-an-accepted-intent`, `spec-with-a-conflict` and `spec-waits-for-the-merge`.
- A test in `tests/test_evals.py` that runs every case's scaffold and lints what it built.
- `README.md` and `CLAUDE.md` gain the skill and `just eval --tag <skill>`.

The plan's step 2 says what each case's repository holds and what its patterns and its judge check.

## Done when

- `just check` passes, with the shape check reading two skills and five cases, and the new test linting every scaffold's documents.
- `just eval --tag generating-a-spec` runs the three cases three times each, and its report is in the pull request.
- In the acting cases, patterns that open `spec.md` by path show a row for each constraint, one question answered and one carried, an owner on every concern, the planted module named, and `- replaces:` on the requirement that ends one in force.
- In the case that stays out, no `spec.md` exists and no `spec/` branch was made by hand.
- R12 is shown in a live session on a copy of the repository, and the pull request says how that went and that R13 was not shown.
