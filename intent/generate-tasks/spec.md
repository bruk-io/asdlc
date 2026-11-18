---
kind: spec
---
# Spec: Tasks for an accepted plan, as a pull request

## Requirements

R1 to R24 describe one skill, and R25 is about the eval cases that judge it. "The skill does X" means Claude does X in the conversation with the skill loaded. "A task" is a `task.md` the skill wrote, and "the pull request" is the one it opens from `tasks/<slug>`. This intent creates no subagent, and changes nothing in the `asdlc` package.

Three words are used throughout. A step is **handed over** when the plan says `- intent: <child>` under it. A step **waits** when it has an open product question and is not handed over. Any other step is **specified**.

### R1: The plugin has a skill, `generating-tasks`, that loads when someone asks for the tasks of an intent

It loads on a plain request. Nobody has to name it.

### R2: The skill makes the branch with `asdlc branch new` and each task with `asdlc task new`, and writes only a task's body

The path, the branch and the frontmatter are the commands': `step` and `delivers` from the plan's step, `size` and `depends` from the flags the skill passes. Claude does not type frontmatter and does not edit it. To change a task's step, size, `depends` or name before the pull request is merged, the skill removes the file, runs `asdlc task new` again with the right flags, and puts the body back. A task whose `depends` named a renamed task is cut again the same way.

### R3: The skill cuts no task for an intent whose plan is not on `main`

`asdlc branch new tasks/<slug>` refuses. The skill says which merge it waits for, and makes no file and no branch by hand.

### R4: Every specified step has a task cut from it, unless R7 holds the plan

A plan that could be built in a single pass still gives a task for each step.

### R5: A step gives one task, unless it is split under R10, R11 or R12, or has a spike under R13

A step with a spike has the spike and, after a later pass under R15, the tasks cut behind it. Two steps are never folded into one task. A plan with one step gives one task, unless that step is split or has a spike. Independent work inside a step never causes a split: size and unknowns do. Once a 5 or an 8 is being split under R11, it may be split along its independent work.

### R6: A step that waits gets no task, and the skill names the step and the question

A step has an open product question when the plan says it waits on an area of concern in the spec, or when "What to build" cannot be written without deciding what the product does. In the second case the skill writes the question out, so the person can judge whether it is one. A question about how to build something is an unknown, not a product question, and is handled by R12 and R13.

### R7: When any step waits, the skill cuts no task for that plan

The owner decided this in C1. The skill leaves no branch behind, and says what has to be on `main` first, with the commands: the child intent, started with `asdlc intent new <child> --parent <slug>`, and the plan's step saying `- intent: <child>`, changed on `plan/<slug>`.

### R8: A step that is handed over gets no task and holds nothing up

That is so even when its text still says it waits on an area of concern. The skill cuts the other steps' tasks, and the handed-over step's line under R20 names the child intent.

### R9: Every task has a size of 1, 2, 3, 5 or 8

Each size means what the intent's table says. The skill carries that table word for word.

### R10: A step that would be bigger than one 8 is split into tasks cut from that step

Every piece has the step's number as its `step`.

### R11: Before cutting a 5 or an 8 the skill tries to split it

When it does not split one, it says why not, where R20 says.

### R12: When unknowns dominate a step and the rest of it can be sized with confidence without the answer, the unknown sits in a first slice

The other pieces are cut in the same pull request, each with a size, and each depends on the first slice.

### R13: When unknowns dominate a step and the rest of it cannot be sized with confidence without the answer, a spike is the only task cut from that step

The owner decided this in C2. A spike's title starts with "Spike:". Its "What to build" is the question, and says the rest of the step is cut once it is answered. Its "Done when" names the file where the answer is written, a path outside `intent/`, because the guard lets a task's branch add no other document.

### R14: A task of another step that needs the work behind a spike is cut in the same pull request as the spike

Its `depends` names the spike, and its "What to build" says it also waits for the tasks cut after the spike, which have no name yet.

### R15: Asked again for a plan that has tasks, the skill cuts only for a specified step with no task, or whose tasks are all merged spikes

It changes no task that exists and cuts no second task for a step that has one. For a step behind a spike it reads each spike's answer from `main` before it sizes anything, so what the spikes taught goes into the new sizes and no accepted size changes. When an answer leaves the rest still impossible to size, what it cuts is another spike. A new task's number follows the highest one on `main`. When there is nothing to cut, it says why and leaves no branch behind.

### R16: A task of size 8 says it gets a plan of its own, and which risk that plan talks through

Its "What to build" says the task's first commit is its own plan, started with `asdlc plan new <slug>/<task>`, and names the risk. Its "Done when" has that plan as a criterion.

### R17: A task names another under `depends` when it needs what that one builds, and for no other reason except R14

Under R14 a spike stands in for work that is not cut yet. Two tasks that change the same file do not depend on each other for that reason. A task with no `depends` can start as soon as it is on `main`.

### R18: Each size has a reason in complexity, unknowns and risk, and no size and no reason for one is given in hours, days or weeks

### R19: A task's "What to build" and "Done when" are enough for someone who never saw the conversation to start, and to review

"What to build" names the files, the functions and the plan's step. A piece of a split step, and a spike, says which part of the step it is, because its `delivers` is the whole step's. A 5 or an 8 says what makes it one. Each line of "Done when" is one a reviewer can answer yes or no to. A task's body has no heading that starts `### R`, `### Q`, `### C` or `### Step` followed by a number: lint reads those as cited headings, and a task has none.

### R20: Every step of the plan is accounted for, in the draft and in the pull request's description

One line for each step: the task or tasks cut from it with their sizes and the reason for each size; for a split step, why it was split; for a 5 or an 8, why it was not split; for a handed-over step, its child intent; for a step behind a spike, that the rest is cut after it.

### R21: `asdlc document check` is clean on the tasks the skill wrote

### R22: The tasks branch changes no file but the new `task.md` files

A task that is already on `main` is not changed, and so its size is not changed. Asked to resize one, the skill says a size records what was known when the task was accepted, and changes nothing.

### R23: The skill shows the draft and applies corrections before anything is pushed

The draft is every task's body with its step, size and `depends`, and the lines R20 asks for.

### R24: The skill opens a pull request and never merges it

### R25: The skill has an eval case where it must act and one where it must stay out

`just check` already fails without them.

## Design

### The skill

`plugins/asdlc/skills/generating-tasks/SKILL.md` (new) (R1). It is a skill for the reason the first three are: the tasks are written with the person who will accept them. It follows `plugins/asdlc/skills/generating-a-plan/SKILL.md` step for step, so the four skills read alike.

With the skill loaded, Claude works in this order:

1. Run `asdlc branch new tasks/<slug>` (R2). It makes the branch from `main`, so what is read next is what was accepted.
   - When it refuses because the plan is not on `main`, say which merge the tasks wait for and stop (R3).
   - When it fails because `tasks/<slug>` already exists, the branch is left from an earlier pass. `main` holds everything on it when `git rev-list --count main..tasks/<slug>` prints 0. `git branch -d` alone is not that test: it also deletes a branch that is merged only to its own upstream, such as one with an open pull request. When the count is 0, switch to `main` if the session is on the branch, delete it with `git branch -d`, and run the command again. When it is not, stop and say the branch holds commits `main` does not, and that the tasks can be asked for again once its pull request is merged and `main` is up to date, or it is closed and the branch deleted.
2. Read `intent/<slug>/intent.md`, `spec.md` and `plan.md`, and the files the plan lists. Run `asdlc task list <slug>` to see which tasks exist and which are done, and read the answer of each merged spike from the file its "Done when" names (R15).
3. Go through the steps in order and decide, for each:
   - whether it is handed over (R8), has a task already (R15), or waits (R6). If any step waits, say which and why, say what has to be merged, switch back to `main`, delete the branch just made with `git branch -d`, and stop (R7). If no step waits and there is nothing to cut, say why, and leave no branch behind in the same way (R15);
   - its size, from the intent's table (R9), by complexity, unknowns and risk (R18);
   - whether it is split, and under which of R10 to R13;
   - what it needs that another task builds (R14, R17). The skill reads the plan's "Files that change" and each step's text to see what overlaps. That is best effort. A shared file alone is not a dependency, and no list of files is written on a task.
4. Run `asdlc task new <slug>/<nn>-<name> --step <n> --size <s> --depends <task> --title <title>` once for each task (R2). `--depends` takes the other task's folder name alone, `<nn>-<name>`, once for each task it depends on. `<nn>` counts the tasks in the order they would be built, and on a later pass goes on from the highest on `main`.
5. Write each task's body: "What to build" and "Done when" (R13, R14, R16, R19). Leave the frontmatter alone.
6. Run `asdlc document check <slug>` (R21). A `heading` finding on a task is about its body, where a line reads as a cited heading, and is fixed in the body (R19). Everything else lint prints about a task is about its frontmatter or about a step with no task, and is fixed by cutting again as R2 says.
7. Show the draft (R20, R23). Apply what the person corrects, by R2's path when the correction is to a step, a size, a `depends` or a name.
8. Commit the `task.md` files alone, with the subject `Tasks: <the intent's title>`. Run `asdlc branch check` (R22). Push, open the pull request with R20's lines as its description, and stop (R24).

A split step's pieces, and a spike, all carry the step's whole `delivers` list, because `asdlc task new` copies it and the skill does not edit frontmatter. `_progress` in `src/asdlc/domain/requirements.py` calls a requirement built only when every task that delivers it is done, so that is right once every piece exists, and wrong for a while after a spike (C2).

Steps 1 and 3 follow what the owner decided in C1 and C2, and R7 and R13 are the requirements that rest on those decisions.

### What the commands already do

Nothing in `src/asdlc` changes. Read in `src/asdlc/cli.py`, `src/asdlc/domain/guard.py`, `src/asdlc/domain/lint.py`, `src/asdlc/domain/tasks.py` and `src/asdlc/domain/documents.py`:

- `branch new tasks/<slug>` makes the branch from `main`. It refuses with "intent/<slug>/plan.md is not on main yet" when the plan is not merged (R3), and fails when the branch exists.
- `task new <slug>/<task> --step <n>` stays on `tasks/<slug>` when that is the current branch. Run from another branch it switches to an existing `tasks/<slug>` as it is, however far behind `main`, which is why the skill starts with `branch new`.
- `task new` writes `intent/<slug>/tasks/<task>/task.md` from `src/asdlc/templates/task.md`, with `step`, `delivers` copied from the step, and `depends` and `size` from its flags, written as given (R2). It refuses a step the plan does not have, and a task that already exists, which is why a correction removes the file first.
- The guard allows `tasks/<slug>` to change only `intent/<slug>/tasks/<task>/task.md` (R22). It does not allow `plan.md`, a task's own `plan.md`, or another intent's files. On `task/<slug>/<task>` it allows any file outside `intent/` and the task's own `plan.md`, and no other new document (R13).
- `parse` looks for cited headings in every document's body, a task's too. A task has none, so `### Step 1: ...` in a task's body is a `heading` finding, and so is a line such as `### R1 notes` (R19). Lint reads nothing else in a task's body, so a placeholder left from the template is not a finding.
- Lint's `step` rule finds a task cut from a step the plan does not have, `delivers` one that delivers a requirement no spec has, and `depends` one that names anything but the folder of another task of the intent.
- Lint's `coverage` rule: once a plan has any task, every step needs a task or a `- intent: <child>` line. Several tasks may share one step, so a split needs nothing new, and a handed-over step needs no task (R8, R10).
- Lint's `child` rule: a step's `- intent: <child>` needs that intent to exist and to name this one as its parent. `asdlc intent new <child> --parent <slug>` writes that.
- A task is `ready` when every task under its `depends` is merged, and an intent is `built` when every task it has is merged. Neither knows of a task that is not cut yet (C2).

Lint does not read `size`: the key is optional and takes any value. That stays, and so do the seven tasks on `main`. R9 is the skill's to do and an eval pattern's to check (C5).

### The eval cases

Five cases under `plugins/asdlc/evals/` (each a new `case.yaml` and `scaffold.sh`), in the format the plan skill's cases use. Each scaffold builds a repository with its documents already in git.

The skill chooses each task's folder name, and a grader that opens a file needs its exact path, as every such grader in the existing cases has. So no grader here opens a `task.md`. Graders read three things:

- the `asdlc task new` command lines, with `tool_used` patterns. By R2 a task's step, size, `depends` and title are all on its command line;
- the set of files the run created, with `target: files` patterns, for how many `task.md` files there are and that nothing else was written;
- the answer, where R23 has the skill show every body and the line for each step.

A judge reads the answer too. A pattern on a command line shows what was asked of the command. It cannot relate two tasks to each other by name, so "this task depends on that one" is checked as "the command for this step has a `--depends`", and lint's `depends` rule makes it a task of the intent.

- `tasks-from-an-accepted-plan` acts. `main` holds an intent, its spec and a plan of three small steps. The third needs what the first builds. The second needs nothing from the others and changes a file the first also changes. Patterns check that `asdlc task new` ran with `--step 1`, `--step 2` and `--step 3` (R4), that exactly three `task.md` files and nothing else were created (R2, R5, R22), that every `--size` is 1, 2, 3, 5 or 8 (R9), that the command for step 3 has a `--depends` and the command for step 2 has none, which is Q1's answer (R17), that the answer has no placeholder from the template (R19) and gives no size in hours, days or weeks (R18), that the answer has a line for each step (R20), and that nothing was pushed. A judge checks the rest of R19.
- `tasks-with-a-spike` acts. Step 2 of three holds an unknown, and the plan's text makes plain that the rest of the step cannot be sized until it is answered. Step 3 needs what step 2 builds. Patterns check that one `task new` ran with `--step 2`, that its title starts with "Spike:" (R13), that the command for step 3 has a `--depends` (R14), and that exactly three `task.md` files were created. A judge checks that the spike's "Done when" names where the answer is written, and that step 3's task says it also waits for what is cut after the spike.
- `tasks-with-a-handed-over-step` acts. Step 2 of the plan says `- intent: <child>`, its text still says it waits on `C1`, and the child intent is on `main` with this intent as its parent. Patterns check that `asdlc task new` ran with `--step 1`, that none ran with `--step 2`, that exactly one `task.md` was created, and that the answer names the child intent (R8). This is the only case that shows the route C1 decided comes to an end.
- `tasks-with-an-open-question` stays out. One step of the plan says it waits on `C1` in the spec and is not handed over. Patterns check that no `task.md` was created, that the answer names the step and gives `asdlc intent new` with `--parent`, and that `git branch -d tasks/` ran, so no branch is left behind (R6, R7).
- `tasks-wait-for-the-merge` stays out. The plan is on the branch `plan/<slug>` and not on `main`. Patterns check that no `task.md` was created, that no `tasks/` branch was made by hand, that Claude merged nothing, and that the answer says the plan has to be merged first (R3).

C6 lists the requirements no case checks. `tests/test_evals.py` needs no change: it already finds every skill and case, and lints what each scaffold builds. `README.md` gains the skill in its table, and loses the line that says cutting tasks is done by hand.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The task format and its lint stay as they are today. | No requirement changes them. Nothing under `src/asdlc` changes. C5 says what that leaves unchecked. |
| `asdlc task new` keeps working as it does today. | R2 uses it as it is. A split step needs no new flag, and a correction is made by cutting the task again. |
| The guard on the tasks branch keeps working as it does today. | R22. The guard is not changed, which is why R7, R13 and R16 are written as they are (C1, C2, C4). |
| The seven tasks already on `main` stay valid. | Nothing in the format or in lint changes, and R22: the skill changes no task on `main`. |
| A skill lands with an eval case where it acts and one where it stays out. | R25. |
| The skill never merges. | R24. The skill stops once the pull request is open. |
| The work stays as close as it can to Anthropic's AI-native SDLC course, whose lesson on parallel sessions says "The engineer splits the work into tasks that touch different files, using the plan from the plan mode play (Stage 3: Build) to see where the work is independent.", "Tasks that share files run in a single session, one after another." and "Each parallel task gets its own worktree", and whose lesson on plan mode says "With a solid plan, the implementation is often a single pass." | Met in part. The plan is what the skill reads to see where the work is independent (R17), and a task with no `depends` can be built in a worktree of its own. Not met for "Tasks that share files run in a single session, one after another": the requester decided in Q1 that two tasks may change the same file. A single pass is not one task (R4), decided in Q2. C3 says what the departure costs. |
| A step that still has open product questions becomes a child intent, not a task. | R6, R7 and R8. The skill cuts no task for it, says a child intent is needed and how to start it, and once the step is handed over cuts the rest. It does not write the child intent itself (C1). |
| A step that is specified becomes a task. | R4, unless R7 holds the plan: while another step waits, a specified step's task waits with it (C1). |
| A step that is specified but large also gets a plan of its own. | R16. Large is an 8 that could not be split, by the requester's answer to Q3. The task says it gets a plan and which risk the plan talks through. The plan itself is written when the task is built (C4). |
| Size is by complexity, unknowns and risk, never by time. | R18. |
| A task's size is 1, 2, 3, 5 or 8 story points, and each size means what the table under this list says. | R9, with R11 and R16 for what the table says of a 5 and an 8. |
| An 8 is the largest task. Anything that feels bigger is not a task yet and is broken down. | R10. |
| When unknowns dominate the estimate, a spike comes first and the work is sized after it. | R13, when the rest cannot be sized without the answer. R15 sizes it afterwards, in a second pull request (C2). When the rest can be sized with confidence, R12 applies, which is the next constraint's first slice. |
| A task is split so that the unknown sits in one piece, either a spike or the first slice. The other pieces can then be sized with confidence. | R12 and R13. |
| A size is not changed once its task is accepted. It records what was known at the time, and what was learned goes into the next sizing. | R22 for the first half. R15 for the second: a later pass reads what a spike taught before it sizes. |

## Open questions from intent

### Q1: The course has the engineer split by which files each piece touches. Our plans are split into steps, and a task is cut from one step. What should happen when two steps touch the same file, or when one step holds work that is independent?
- answer: answered

From the requester, when the spec was asked for. A file is not limited to one task. Two tasks may change the same file, and a conflict is resolved on the branch that merges second, the way developers normally would. A task is cut from a step, and depends on another only when it needs what that one builds (R17). The skill reads the plan to see what overlaps, as best effort: there is no list of files on a step or on a task, and no lint rule. Resolving a conflict is the worker's job, and the worker is a later intent. Independent work inside one step stays in that step's task (R5). The requester chose this knowing it departs from the course's line that tasks sharing files run one after another.

### Q2: Should a plan that is a single pass become one task, or still one task for each step?
- answer: answered

From the requester. Still one task for each step. A single-pass plan is not collapsed into one task, and a plan with one step gives one task. A step gives more than one task only when it is too big for one and is split, as the intent's sizing rules say (R4, R5).

### Q3: Where is the line between a task that is large and gets a plan of its own, and a step that should have been a child intent?
- answer: answered

From the requester. A step with an open product question becomes a child intent (R6). Anything else is a task. An 8 is split when it can be, and an 8 that cannot be split also gets a plan of its own (R10, R11, R16).

## Areas of concern

### C1: One step with an open product question holds up every task of the plan
- owner: Bruk Habtu

Decided as proposed by the owner, Bruk Habtu, on 2026-11-17. What follows says what the conflict is, what was decided and what it costs.

Four things the intent asks for cannot all hold in one pull request. A step with an open product question becomes a child intent and not a task. Lint is clean on the pull request. The guard on the tasks branch and the lint stay as they are. A person asks for the tasks and gets a pull request.

Lint's `coverage` rule fails a plan as soon as it has one task and a step with neither a task nor `- intent: <child>`. The `child` rule needs that child intent to exist with this intent as its parent. On `tasks/<slug>` the guard allows `task.md` files only, so the skill can add neither the child intent nor the line in the plan. Cutting the other steps' tasks and leaving the step out gives a pull request that fails lint.

Decided, and what R7 requires: the skill cuts nothing. It names the step and says what has to be merged first: the child intent, captured on `intent/<child>` with `asdlc intent new <child> --parent <slug>`, and the plan's step changed to say `- intent: <child>` on `plan/<slug>`. The person asks for the tasks again after those two merges. The cost is that the first outcome is not met for such a plan until two more pull requests are merged. It also means a specified step of that plan has no task in the meantime, which is the exception R4 states.

The route ends at R8: once the step is handed over it holds nothing up, and the other steps' tasks lint clean without a task for it.

The other ways through are to let the pull request fail lint until the child intent lands, or to change the guard or the `coverage` rule. Each breaks something the intent says to keep.

The skill does not write the child intent, and the route leans on two things no skill does today. The `capturing-intent` skill runs `asdlc intent new` without `--parent`, and without a parent lint's `child` rule fails the plan's new line. So R7 has the skill give the command with `--parent`, and the person has to see that it is used. The `generating-a-plan` skill has no stated way to change a plan that is on `main`: its first step, `asdlc plan new`, fails on a `plan.md` that exists, so the `- intent: <child>` line is added by hand on `plan/<slug>`. Neither skill is changed here.

### C2: After a spike, the rest of the step's tasks need a second pull request
- owner: Bruk Habtu

Decided as proposed by the owner, Bruk Habtu, on 2026-11-17. What follows says what the conflict is, what was decided and what it costs.

The intent says a spike comes first and the work is sized after it, and that a size is not changed once its task is accepted. So the work behind a spike cannot be in the same pull request with a size on it.

Decided, and what R13 requires: the spike is the only task cut from that step, which satisfies lint's `coverage` rule. Its "What to build" says the rest of the step is cut once it is done. The person then asks for the tasks again, and the skill adds them on `tasks/<slug>` in a second pull request (R15).

A task of another step that needs what the uncut work builds cannot wait for that second pull request: its step would have no task, and lint's `coverage` rule would fail the first one. Its `depends` cannot name a task that does not exist yet, and R22 keeps it from being changed later. So R14 cuts it in the first pull request, depending on the spike, with the rest of what it waits for said in its body.

That leaves three costs. `asdlc task list` shows that task as `ready` as soon as the spike is merged, though the work it needs is not cut, and only its body says so. Between the spike's merge and the second pull request, `asdlc requirement list` shows the step's requirements as built, and when the spike is the last task merged `asdlc intent list` shows the whole intent as built. And the outcome "holding the tasks for that plan" is met in two parts.

The branch left from the first pull request is not a cost any more: the skill starts with `asdlc branch new`, which fails on a branch that exists where `asdlc task new` would switch to it as it is, behind `main`.

### C3: Two tasks built at the same time can change the same file, and nothing says so
- owner: Bruk Habtu

Decided by the requester in Q1, and written here for its cost. The course has tasks that share files run one after another. Here they may run at once, the second to merge resolves the conflict, and no task and no lint rule records the overlap. The skill's reading of the plan for overlap is best effort. Until the worker intent says how a worker resolves a conflict, a person does it.

### C4: A task of size 8 says it gets a plan of its own, and nothing checks that it does
- owner: Bruk Habtu

The guard does not let `tasks/<slug>` add `intent/<slug>/tasks/<task>/plan.md`, and `asdlc plan new <slug>/<task>` works on `task/<slug>/<task>`, which waits for the task's merge. So the plan cannot be in the tasks pull request. R16 puts it in the task's "Done when". The task format has no key for it and stays as it is, and the guard does not judge that a plan was committed before the code. Whoever reviews the task's pull request is the only check.

### C5: Only the skill holds a size to 1, 2, 3, 5 or 8, and keeps an accepted size from changing
- owner: Bruk Habtu

Lint does not read `size`, and the intent keeps lint as it is. The guard lets `tasks/<slug>` change a `task.md` that is already on `main`. A task written by hand, or by a session that did not load the skill, can have a size of 13 or none, or a new size on an accepted task, and lint and the guard are clean.

### C6: No eval case checks ten of the requirements
- owner: Bruk Habtu

An eval run is one turn with no network, and each scaffold holds one situation. No case checks:

- R6's second test, a product question the plan does not mark. It stops a whole plan on the skill's judgment, and only the question it writes out lets a person check it.
- R10: no scaffold has a step bigger than an 8.
- R11: no scaffold has a 5 or an 8 to try to split.
- R12: no scaffold has a first slice. The one case with an unknown is a spike.
- R15: no scaffold has tasks already, or a merged spike, or a branch left from an earlier pass.
- R16: no scaffold has an 8.
- R21: a grader can show that `asdlc document check` ran, and not that it printed nothing.
- R22's refusal to resize an accepted task.
- R23's corrections, and so R2's path for changing a size or a `depends`.
- R24, and the pull request's description that R20 asks for. The same lines in the draft are checked.

As with the first three skills, R23 and R24 are shown by using the skill in a live session on this repository's next plan. That shows only what that plan happens to hold, so R10, R11, R12, R15 and R16 may be shown by nothing until a plan has such a step.

R19, and what the spike case asks of a task's body, need a judge, and a judge's verdict varies between runs. No case rests on a judge alone.
