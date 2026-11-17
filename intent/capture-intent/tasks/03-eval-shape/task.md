---
kind: task
step: 3
delivers: [R14, R15]
size: 2
---
# Task: just check judges the shape of the eval cases

## What to build

Step 3 of the plan. `tests/test_evals.py` reads the folder names under `plugins/asdlc/skills/` and every `plugins/asdlc/evals/*/case.yaml`, and fails, naming the skill or the case, when:

- a skill has no case tagged with its name and `acts`, or none tagged with its name and `stays-out`;
- a case has no grader of type `regex` or `file_exists`.

The two rules are one function that takes the skills' names and the parsed cases and returns what is wrong. `pyyaml` joins the `dev` group in `pyproject.toml`.

## Done when

- The function's own tests, on made-up cases, show each rule failing and a complete set passing.
- The test over the real folders passes with no skill present.
- click is still the only runtime dependency.
- `just check` passes.
