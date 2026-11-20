---
kind: task
step: 6
delivers: [R21, R22, R23, R24, R25, R26, R27, R28, R29, R30, R31, R34, R35]
depends: [04-start-undone, 05-task-start-resume, 07-stop-merges, 08-stop-comment, 09-stop-commit-rules]
size: 8
---
# Task: the building-a-task skill, its two cases, and the README

## What to build

Step 6 of the plan, in one pull request: the skill, the two eval cases `just check` needs, a test that runs the commands in each scaffold with no model, and the README.

This task is started with `asdlc task start building-a-task/10-skill-and-two-cases` and ended with `asdlc task stop`, not by hand. It is the first task built with the two commands against GitHub itself.

**Its first commit is a plan of its own.** The task is an 8. So after the start, run `asdlc plan new building-a-task/10-skill-and-two-cases`, write `intent/building-a-task/tasks/10-skill-and-two-cases/plan.md`, commit it alone, run `asdlc task stop building-a-task/10-skill-and-two-cases`, which prints `plan`, and stop. Write nothing else until a person has read that plan on the pull request and asks for the task to be picked up, which is `asdlc task start --resume`.

The risk that plan talks through is that the eval cases may not run as designed (C8 in the spec). Nobody has run `asdlc task start` or `asdlc task stop` inside an eval run. Three things are not known: whether the two commands run there at all, whether the run's folder still reads as clean to `task stop` once the model has written a file, and what the sandbox does to the push with `-u`. The plan says how the pilot settles each, what the pilot costs, and what is done for each answer. It also covers a second risk: a fault in tasks 03 to 09 that only GitHub shows is met here first.

Then, in the order the intent's plan gives in step 6:

- `plugins/asdlc/skills/building-a-task/SKILL.md` (new). Load `authoring-kit:authoring-skills` before writing it. Its frontmatter is what the spec's Design gives, field for field: a `description`, `argument-hint: <slug>/<task>`, and `allowed-tools` with `Bash(asdlc task show *)`, `Bash(asdlc task list *)`, `Bash(asdlc plan new *)` and `Bash(asdlc task stop *)`. Not `asdlc task start`. No `context`, no `disable-model-invocation` and no `hooks`. Its body is the seven steps of the spec's Design under numbered headings, and holds the wording for all of R22 to R34, the parts task 11 judges (R32 and R33) included.
- `plugins/asdlc/evals/build-a-ready-task/`, a `case.yaml` and a `scaffold.sh`, tagged `building-a-task` and `acts`.
- **The pilot, before any other grader.** Write that case with the `skill-loaded` grader alone, run `just eval --case build-a-ready-task --runs 1 --ablation none`, and read what the run wrote. When the commands cannot run inside an eval run, stop, and say so on the pull request with `asdlc task stop --message`: the cases cannot be written as designed, and that is for the owner of C8 to decide.
- `plugins/asdlc/evals/build-waits-for-the-merge/`, a `case.yaml` and a `scaffold.sh`, tagged `building-a-task` and `stays-out`.
- `tests/test_evals.py` gains a test that builds each new scaffold and runs the commands in it with no model, as the plan gives it.
- `README.md`: a row for the skill in the table under "Skills and their evals", "Four skills" becomes five, the built list gains `task start`, `task stop` and `.asdlc/checks`, and the line "**The other skills.**" says what is still not built.

The plan's step 6 says what each scaffold's repository holds, what the stand-in for `gh` records, and what each grader checks. Each scaffold is written out in full with plain git, with its bare repository and its stand-in under `.git/`, and a `.gitignore` on `main` for `.claude/` and `__pycache__/`. Whether the builder ran a command is always a `tool_used` grader on Bash. What a file holds is always a `regex` with `source: file` at its exact path.

When a pilot run shows the skill's wording does not hold, change the wording, not the grader.

It is an 8 for three reasons. It is more than the earlier skill tasks, which were 5s: the scaffolds carry a remote and a stand-in, and there is a new kind of test. It holds the unknowns above, and one of them can stop the task. And seven things the skill says are judged by no case (R25, R26, R27, R28, R29, the `--resume` half of R22 and the split R33 proposes), so a fault in that wording is found only by reading. It is not split, because `just check` fails on a skill that lands without a case where it acts and one where it stays out.

## Done when

- The task's own `plan.md` is the first commit after the start and changes nothing else, and `asdlc task stop` printed `plan` for it.
- `just check` passes, with the shape check reading five skills, both new scaffolds' documents linted, and the new test running the commands in both scaffolds. Its output is the comment `asdlc task stop` posted.
- The pull request says what the pilot run showed about each of the three unknowns.
- Each of the two cases was piloted with one run before the full three, and `just eval --tag building-a-task` ran them three times each, with its report in the pull request.
- In `build-a-ready-task`: the skill loaded; `asdlc task start claim-steps/01-step-name` and `asdlc task stop` ran; no `git worktree add`, no `git switch`, `git checkout` or `git branch` that names `task/`, no `git push`, no `gh pr create`, no `gh pr merge` and no `gh pr ready` ran; `portal/adjuster_view.py` holds the new line and `.git/HEAD` names the task's branch; the answer holds the pull request's link and `ready`; and the stand-in's record has a draft opened, a comment and a `ready`.
- In `build-waits-for-the-merge`: `.git/HEAD` names the branch the scaffold left; no branch or worktree for the task was made; nothing was merged; the run created no path outside `.git/` apart from `__pycache__/`; the record has no create, comment or ready; and the answer says "merge".
- The skill's frontmatter has no `context`, no `disable-model-invocation` and no `hooks`, and its `allowed-tools` does not hold `asdlc task start`.
- The pull request lists the seven things no case checks, each with the lines of the skill that carry it.
- The pull request says how `asdlc task start`, `asdlc task start --resume` and `asdlc task stop` behaved against GitHub while this task was built with them.
