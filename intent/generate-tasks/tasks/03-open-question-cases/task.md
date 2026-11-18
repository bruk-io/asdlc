---
kind: task
step: 3
delivers: [R6, R7, R8]
depends: [01-skill-and-two-cases]
size: 3
---
# Task: the two eval cases for a step with an open product question

## What to build

Step 3 of the plan: two eval cases. It needs task 01's skill, and nothing from task 02.

- `plugins/asdlc/evals/tasks-with-a-handed-over-step/`, a `case.yaml` and a `scaffold.sh`, tagged `generating-tasks` and `acts`. Its scaffold merges a spec whose `C1` is an open product question, a second intent with `parent: claim-steps` in its frontmatter, and a plan of two steps. Step 2 of that plan has `- intent: <child>` under its `- delivers:` line, and its text still says it waits on `C1`.
- `plugins/asdlc/evals/tasks-with-an-open-question/`, a `case.yaml` and a `scaffold.sh`, tagged `generating-tasks` and `stays-out`. The same spec, and a plan whose step 2 says it waits on `C1` and has no `- intent:` line. No child intent exists.
- `README.md`: the count of eval cases goes up by two.
- `plugins/asdlc/skills/generating-tasks/SKILL.md`, only when a pilot run shows the skill's wording does not hold. Change the wording, not the grader.

The plan's step 3 says what the patterns check. Task 02 can be built at the same time and may change the same two files, the skill and the README's count. Whichever merges second resolves the conflict.

This is a 3: two cases of a shape task 01 sets. The uncertain part is the scaffold for the handed-over step, which has to lint clean with a child intent and a plan that points to it.

## Done when

- `just check` passes, with both new scaffolds' documents linted.
- Each case was piloted with one run, then run three times, and the report is in the pull request.
- In `tasks-with-a-handed-over-step`: `asdlc task new` ran with `--step 1`, none ran with `--step 2`, exactly one `task.md` was created, and the answer names the child intent.
- In `tasks-with-an-open-question`: no `task.md` was created, the answer names step 2 and gives `asdlc intent new` with `--parent claim-steps`, and `git branch -d tasks/claim-steps` ran.
- If the skill's wording changed, the pull request says what changed and which run showed the need.
