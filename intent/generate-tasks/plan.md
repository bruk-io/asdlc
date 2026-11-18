---
kind: plan
---
# Plan: Tasks for an accepted plan, as a pull request

## Files that change

- plugins/asdlc/skills/generating-tasks/SKILL.md (new)
- plugins/asdlc/evals/tasks-from-an-accepted-plan/case.yaml (new)
- plugins/asdlc/evals/tasks-from-an-accepted-plan/scaffold.sh (new)
- plugins/asdlc/evals/tasks-wait-for-the-merge/case.yaml (new)
- plugins/asdlc/evals/tasks-wait-for-the-merge/scaffold.sh (new)
- plugins/asdlc/evals/tasks-with-a-spike/case.yaml (new)
- plugins/asdlc/evals/tasks-with-a-spike/scaffold.sh (new)
- plugins/asdlc/evals/tasks-with-a-handed-over-step/case.yaml (new)
- plugins/asdlc/evals/tasks-with-a-handed-over-step/scaffold.sh (new)
- plugins/asdlc/evals/tasks-with-an-open-question/case.yaml (new)
- plugins/asdlc/evals/tasks-with-an-open-question/scaffold.sh (new)
- README.md

## Order of work

Nothing under `src/asdlc` changes, and neither does `tests/test_evals.py`: it already finds every skill and case, and lints what each scaffold builds. The work is one skill, five eval cases and the README.

Step 1 writes the whole skill, with the two cases `just check` fails without. Steps 2 and 3 each add the cases that judge one part of the skill, and each needs step 1's skill to run against. Steps 2 and 3 need nothing from each other. A requirement is on the step whose case judges it, so it is not called built until that case is there.

All five scaffolds build their repository with plain git and write their documents out in full, as `plugins/asdlc/evals/plan-from-an-accepted-spec/scaffold.sh` does. They start from its repository: the modules `claims_gateway.py` and `portal/adjuster_view.py`, the test `tests/test_adjuster_view.py`, and the intent `claim-steps` with its spec of R1, R2 and R3, each merged with `git merge --no-ff`. Each prompt asks for the tasks of `claim-steps` and says nothing else. Each `case.yaml` follows `plugins/asdlc/evals/plan-from-an-accepted-spec/case.yaml`: `schema_version: "1.1"`, `runs: 3`, and `allowed_tools: [Skill, Bash, Read, Write, Edit, Glob, Grep]`.

No grader opens a `task.md`, because the skill chooses each task's folder name. Graders read three things:

- the `asdlc task new` command lines, with `tool_used` graders on `Bash`. A pattern that ties two flags to one command keeps to that command with `[^\n;&|]*` between them, because a run may chain several commands in one call;
- the files the run created, with `target: files` patterns. That target is one path to a line, so "exactly three" is one pattern that finds `^intent/claim-steps/tasks/[^/\n]+/task\.md$` three times and one, with `match: not_contains`, that finds it four times;
- the answer, with a `regex` grader that has no target.

### Step 1: The skill, the two cases `just check` needs, and the README
- delivers: R1, R2, R3, R4, R5, R9, R10, R11, R12, R15, R16, R17, R18, R19, R20, R21, R22, R23, R24, R25

One step, because `just check` fails on a skill that lands without a case where it acts and one where it stays out.

**The skill.** `plugins/asdlc/skills/generating-tasks/SKILL.md`. Its frontmatter is a `description` and `allowed-tools: Bash(asdlc *)`, as `plugins/asdlc/skills/generating-a-plan/SKILL.md` has. The description says what the skill leaves, when it loads (someone asks for the tasks of an intent, or to cut, split or size the work of an accepted plan) and what Claude gets wrong without it (R1). Its body is the eight steps of the spec's design, in that order and under numbered headings, so the four skills read alike. It holds all of R1 to R24 in this step, the parts steps 2 and 3 judge included:

1. Start with `asdlc branch new tasks/<slug>`. Stop when the plan is not on `main` (R3). When the branch exists, test it with `git rev-list --count main..tasks/<slug>` and never with `git branch -d` alone, as the design's step 1 says.
2. Read the intent, the spec, the plan and the files the plan lists. Run `asdlc task list <slug>`, and read each merged spike's answer from the file its "Done when" names (R15).
3. Decide for each step: handed over, has a task, waits, or specified (R4, R6, R7, R8, R15); its size; whether it is split (R5, R10, R11, R12, R13); and what it depends on (R14, R17). The spec's three words, handed over, waits and specified, are defined here as the spec defines them. The intent's size table is copied word for word (R9), with the rule that a size and its reason are never in hours, days or weeks (R18).
4. Run `asdlc task new <slug>/<nn>-<name> --step <n> --size <s> --depends <task> --title <title>` once for each task (R2).
5. Write each body, and nothing in the frontmatter (R2, R16, R19). No heading in a body starts `### R`, `### Q`, `### C` or `### Step` followed by a number.
6. Run `asdlc document check <slug>` (R21). Fix a `heading` finding in the body, and anything else by removing the file and cutting the task again.
7. Show the draft: every body with its step, size and `depends`, and one line for each step of the plan (R20, R23). A correction to a step, a size, a `depends` or a name is made by cutting again (R2). Asked to resize a task that is on `main`, say why not and change nothing (R22).
8. Commit the `task.md` files alone as `Tasks: <the intent's title>`, run `asdlc branch check`, push, open the pull request with the lines for each step as its description, and stop. Never merge (R24).

**`tasks-from-an-accepted-plan`**, tagged `generating-tasks` and `acts`. On top of the shared repository its scaffold merges a `plan.md` of three small steps:

- Step 1 delivers R1: a function `step_name` in `claims_gateway.py` that gives a step's name as the portal shows it, and `status_line` in `portal/adjuster_view.py` returns it.
- Step 2 delivers R3: `fetch_claim` in `claims_gateway.py` takes the adjuster's name. It needs nothing from the other steps, and changes a file step 1 also changes.
- Step 3 delivers R2: a new function in `portal/adjuster_view.py` that lists every step by calling `step_name`, and its text says it needs step 1's function.

Patterns check that:

- the skill loaded, and `asdlc branch new tasks/claim-steps` ran (R2);
- `asdlc task new` ran with `--step 1`, with `--step 2` and with `--step 3` (R4);
- exactly three `task.md` files were created and no other file (R2, R5, R22);
- no `--size` is anything but 1, 2, 3, 5 or 8 (R9);
- the command for step 3 has a `--depends`, and no command for step 2 has one (R17);
- the answer has none of the task template's placeholders, read from `src/asdlc/templates/task.md` (R19), and no size given in hours, days or weeks (R18);
- the answer names step 1, step 2 and step 3 (R20);
- no `git push` and no `gh pr` ran.

A judge reads the answer and passes only when each task's "What to build" names the files and functions, and each line of "Done when" can be answered yes or no (R19).

**`tasks-wait-for-the-merge`**, tagged `generating-tasks` and `stays-out`. The same plan is committed on the branch `plan/claim-steps` and not merged, and the run starts on that branch. Patterns check that no file with `tasks/` in its path was created, that no `git switch`, `git checkout` or `git branch` named `tasks/`, that no `git merge` and no `gh pr merge` ran, and that the answer says "merge" (R3). It follows `plugins/asdlc/evals/plan-waits-for-the-merge/case.yaml` grader for grader.

**`README.md`.** The table under "Skills and their evals" gains a row for `generating-tasks`. Under "What is built, and what is not", "Three skills" becomes four and names the new one, and the count of eval cases becomes ten. The line "**The other skills.** Sizing and cutting tasks are done by hand from the templates." is not taken out and left empty. It is rewritten to say what is still done by hand after this skill: sizing and cutting tasks is a skill now, and building a task is not, because there is no worker yet.

Pilot each case with `just eval --case <name> --runs 1 --ablation none`, and read what the run wrote before changing a grader. When a run shows the skill's wording does not hold, change the wording, not the grader.

### Step 2: The case with a spike
- delivers: R13, R14

Needs step 1's skill. Adds `plugins/asdlc/evals/tasks-with-a-spike/`, tagged `generating-tasks` and `acts`.

Its scaffold merges a plan of three steps. Step 2 holds an unknown about how to build it, not about what the product does, and its text says plainly that the rest of the step cannot be sized until the unknown is answered. Step 3's text says it needs what step 2 builds. Step 1 is small and specified.

Patterns check that:

- exactly one `asdlc task new` command has `--step 2`, and its `--title` starts with "Spike:" (R13);
- the command for step 3 has a `--depends` (R14);
- exactly three `task.md` files were created.

A judge reads the answer and passes only when the spike's "Done when" names a file outside `intent/` where the answer is written, and step 3's task says it also waits for the tasks cut after the spike.

When the pilot run shows the skill's wording for a spike does not hold, this step changes `plugins/asdlc/skills/generating-tasks/SKILL.md` too. The count of eval cases in `README.md` goes up by one.

### Step 3: The two cases for a step with an open product question
- delivers: R6, R7, R8

Needs step 1's skill, and nothing from step 2. Adds two cases, both tagged `generating-tasks`.

**`tasks-with-a-handed-over-step`**, tagged `acts`. Its scaffold merges three things: a spec whose `C1` is an open product question, a second intent `intent/<child>/intent.md` with `parent: claim-steps` in its frontmatter, and a plan of two steps. Step 2 of that plan has `- intent: <child>` under its `- delivers:` line, and its text still says it waits on `C1`. Patterns check that `asdlc task new` ran with `--step 1`, that none ran with `--step 2`, that exactly one `task.md` was created, and that the answer names the child intent (R8).

**`tasks-with-an-open-question`**, tagged `stays-out`. The same spec and a plan whose step 2 says it waits on `C1` and has no `- intent:` line. No child intent exists. Patterns check that no `task.md` was created, that the answer names step 2 and gives `asdlc intent new` with `--parent claim-steps`, and that `git branch -d tasks/claim-steps` ran (R6, R7).

When a pilot run shows the skill's wording does not hold, this step changes `plugins/asdlc/skills/generating-tasks/SKILL.md` too. The count of eval cases in `README.md` goes up by two.

## Risks

- **Step 1 is the riskiest.** It writes all of the skill, and eight of its twenty requirements are judged by no case (C6): R10, R11, R12, R15, R16, R21, R23 and R24. Neither is R22's refusal to resize, nor R2's path for a correction. A fault in that wording is found by a person reading the skill, or not until a plan has such a step.
- **A grader reads command lines, not tasks.** A run that cuts a task, removes it and cuts it again leaves two `asdlc task new` commands for one step, and the spike case's "exactly one command with `--step 2`" would fail a run that did the right thing. The count of `task.md` files is the check on how many tasks there are. If the pilot shows this, that grader's `max` is dropped. That is fixing a grader that judges the wrong thing, not weakening one.
- **A run is one turn.** The skill shows a draft and stops, so no case reaches a correction, a commit or a pull request (C6). The scaffolded plans leave nothing to ask about.
- **The spike case rests on how plain the scaffold's plan is.** If its step 2 reads as an unknown the rest can be sized around, the skill is right to cut a first slice under R12, and the case fails a correct run. The plan's text has to say the rest cannot be sized.
- **Steps 2 and 3 can be built at the same time and share two files** (C3): `plugins/asdlc/skills/generating-tasks/SKILL.md`, when a pilot run sends either back to the wording, and the count of cases in `README.md`. The second to merge resolves the conflict, by hand.
- **The skill tells a person to do two things no skill does** (C1): start the child intent with `--parent`, and add `- intent: <child>` to a plan that is on `main`. `tasks-with-an-open-question` checks that the answer gives the first command. Nothing checks the person can follow the second.
- **After a spike, `asdlc task list`, `requirement list` and `intent list` say more is ready or built than is** (C2). The skill's wording for R13 and R14 is the only place that says so, and step 2's judge is the only check on it.
- **An 8's own plan and a size held to five values are the skill's word alone** (C4, C5). Nothing in this plan adds a check for either, because the intent keeps lint and the guard as they are.
- **The suite grows to thirteen cases.** With three runs each, with the plugin and without it, that is 78 runs. `just eval --tag generating-tasks` runs this skill's five.

## Proof

`just check` passes at the end of every step, with its output in the step's pull request. It shows the shape check found the skill's cases, and that each new scaffold builds a repository whose documents lint clean. Every case is piloted with one run, then run three times with `just eval --tag generating-tasks`, and the report goes in the pull request.

- **R1.** The `skill-loaded` grader in each acting case: a `tool_used` grader on `Skill` matching `generating-tasks`, from a prompt that does not name the skill.
- **R2.** In `tasks-from-an-accepted-plan`: `asdlc branch new` and `asdlc task new` ran, and the three `task.md` files are the only files created. Cutting again for a correction is shown in the live session below.
- **R3.** `tasks-wait-for-the-merge`.
- **R4, R5.** In `tasks-from-an-accepted-plan`: a command for each of the three steps, and exactly three `task.md` files.
- **R6, R7.** `tasks-with-an-open-question`, for a step the plan marks as waiting. R6's second test, a product question the plan does not mark, is shown by nothing (C6).
- **R8.** `tasks-with-a-handed-over-step`.
- **R9.** The `--size` pattern in `tasks-from-an-accepted-plan`. That the table is word for word: `git diff` of the skill against `intent/generate-tasks/intent.md`, read by the reviewer of step 1's pull request.
- **R10, R11, R12, R15, R16.** No case (C6). The reviewer of step 1's pull request reads the skill's step 3 and step 5 against each requirement's text. Each is first seen working when a plan has such a step.
- **R13, R14.** `tasks-with-a-spike`, its patterns and its judge.
- **R17.** In `tasks-from-an-accepted-plan`: a `--depends` on step 3's command and none on step 2's, though steps 1 and 2 change the same file.
- **R18.** The pattern for hours, days and weeks on the answer in `tasks-from-an-accepted-plan`.
- **R19.** The placeholder pattern and the judge in `tasks-from-an-accepted-plan`. Lint's `heading` rule covers the headings a body must not have.
- **R20.** The pattern that the answer names each step, in `tasks-from-an-accepted-plan`, and that it names the child intent, in `tasks-with-a-handed-over-step`. The pull request's description is seen in the live session.
- **R21.** A grader shows only that `asdlc document check` ran. That it printed nothing is seen in the live session.
- **R22.** The files pattern in `tasks-from-an-accepted-plan` shows nothing but `task.md` files was written. The refusal to resize is read in the skill by step 1's reviewer.
- **R23.** A live session, after step 1, on a copy of this repository with this intent's tasks taken out: the skill cuts the tasks for this plan again, shows the draft, and one size is corrected, which also shows R2's path. Step 1's pull request says how that went. This intent's own tasks are cut by hand, because the skill does not exist yet.
- **R24.** Not shown by this plan. The copy has no remote to push to. It is seen the first time the skill is used on this repository's next plan, as C6 says.
- **R25.** `just check`: `test_every_skill_in_the_plugin_has_both_kinds_and_no_case_is_judge_only` in `tests/test_evals.py` reads the new skill and its cases.
