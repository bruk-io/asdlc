---
kind: task
step: 2
delivers: [R13, R14]
depends: [01-skill-and-two-cases]
size: 3
---
# Task: the eval case with a spike

## What to build

Step 2 of the plan: one eval case. It needs task 01's skill to run against.

- `plugins/asdlc/evals/tasks-with-a-spike/`, a `case.yaml` and a `scaffold.sh`, tagged `generating-tasks` and `acts`. On top of the shared `claim-steps` repository its scaffold merges a plan of three steps. Step 1 is small and specified. Step 2 holds an unknown about how to build it, and its text says plainly that the rest of the step cannot be sized until the unknown is answered. Step 3 says it needs what step 2 builds.
- `README.md`: the count of eval cases goes up by one.
- `plugins/asdlc/skills/generating-tasks/SKILL.md`, only when a pilot run shows the skill's wording for a spike does not hold. Change the wording, not the grader.

The plan's step 2 says what the patterns and the judge check. Task 03 can be built at the same time and may change the same two files, the skill and the README's count. Whichever merges second resolves the conflict.

This is a 3. The approach is the one task 01's two cases set. The work is in a scaffold whose plan reads unmistakably as a spike: a step that reads as an unknown the rest can be sized around is rightly cut as a first slice, and then the case fails a correct run.

## Done when

- `just check` passes, with the new scaffold's documents linted.
- The case was piloted with one run, then run three times with `just eval --case tasks-with-a-spike`, and the report is in the pull request.
- Exactly one `asdlc task new` command has `--step 2` and its `--title` starts with "Spike:", the command for step 3 has a `--depends`, and exactly three `task.md` files were created.
- The judge passes only when the spike's "Done when" names a file outside `intent/` for the answer, and step 3's task says it also waits for the tasks cut after the spike.
- If the skill's wording changed, the pull request says what changed and which run showed the need.
