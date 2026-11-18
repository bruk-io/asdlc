---
kind: task
step: 1
delivers: [R1, R2, R3, R4, R5, R9, R10, R11, R12, R15, R16, R17, R18, R19, R20, R21, R22, R23, R24, R25]
size: 5
---
# Task: the generating-tasks skill, its two cases, and the README

## What to build

Step 1 of the plan, in one pull request.

- `plugins/asdlc/skills/generating-tasks/SKILL.md`: frontmatter with a `description` and `allowed-tools: Bash(asdlc *)`, and the eight steps of the spec's design as its body, under numbered headings as the other three skills have. It holds the wording for every requirement from R1 to R24, including the ones tasks 02 and 03 judge (R6, R7, R8, R13 and R14). The intent's size table is copied word for word.
- `plugins/asdlc/evals/tasks-from-an-accepted-plan/`, a `case.yaml` and a `scaffold.sh`, tagged `generating-tasks` and `acts`.
- `plugins/asdlc/evals/tasks-wait-for-the-merge/`, a `case.yaml` and a `scaffold.sh`, tagged `generating-tasks` and `stays-out`.
- `README.md`: the skills table gains a row, "Three skills" becomes four, the count of eval cases becomes ten, and the "The other skills" line says cutting tasks is a skill now and building a task is still done by hand.

The plan's step 1 says what each scaffold's repository holds and what each case's patterns and judge check. No grader opens a `task.md`: they read the `asdlc task new` command lines, the set of files created, and the answer.

This is a 5 and not a 3 for two reasons. The skill carries more rules than any of the other three, and eight of them (R10, R11, R12, R15, R16, R21, R23 and R24) are judged by no case, so a fault in their wording is found only by reading. And the graders work from command lines, which no existing case does, so a pilot run may send a case or the skill's wording back. It is not split, because `just check` fails on a skill that lands without both kinds of case.

## Done when

- `just check` passes, with the shape check reading four skills and ten cases, and both new scaffolds' documents linted.
- Each of the two cases was piloted with one run before the full three, and `just eval --tag generating-tasks` ran them three times each, with its report in the pull request.
- In `tasks-from-an-accepted-plan`: an `asdlc task new` command ran for each of the three steps, exactly three `task.md` files and no other file were created, every `--size` is 1, 2, 3, 5 or 8, step 3's command has a `--depends` and step 2's has none, and nothing was pushed.
- In `tasks-wait-for-the-merge`: no file under a `tasks/` folder was created, no `tasks/` branch was made by hand, nothing was merged, and the answer says the plan has to be merged first.
- The size table in the skill is the same, word for word, as the one in `intent/generate-tasks/intent.md`.
- The pull request lists the eight requirements no case checks, each with the lines of the skill that carry it.
- R23 was shown in a live session on a copy of this repository with this intent's tasks taken out: the skill cut the tasks for this plan, showed the draft, and one size was corrected by cutting the task again. The pull request says how that went, how the skill's cut compares with these three tasks, and that R24 was not shown.
