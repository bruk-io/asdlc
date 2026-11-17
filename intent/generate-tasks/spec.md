---
kind: spec
---
# Spec: Tasks for an accepted plan, as a pull request

## Requirements

R1 to R19 describe one skill, and R20 is about the eval cases that judge it. "The skill does X" means Claude does X in the conversation with the skill loaded. "A task" is a `task.md` the skill wrote, and "the pull request" is the one it opens from `tasks/<slug>`. This intent creates no subagent, and changes nothing in the `asdlc` package.

### R1: The plugin has a skill, `generating-tasks`, that loads when someone asks for the tasks of an intent

It loads on a plain request. Nobody has to name it.

### R2: The skill makes each task with `asdlc task new` and writes only its body

The path, the branch and the frontmatter are the command's: `step` and `delivers` from the plan's step, `size` and `depends` from the flags the skill passes. Claude does not type them, and does not edit them afterwards.

### R3: The skill cuts no task for an intent whose plan is not on `main`

`asdlc task new` refuses. The skill says which merge it waits for, and makes no file and no branch by hand.

### R4: Every step that is specified has a task cut from it

A step is specified when it does not wait on an open product question (R6). A plan with one step gives one task. A plan that could be built in a single pass still gives one task for each step.

### R5: A step gives one task, unless it is split because it is too big for one

Two steps are never folded into one task. Work inside a step that looks independent is not a reason to split it. The only reasons are R9 and R10.

### R6: A step that waits on an open product question gets no task

The skill names the step and says it becomes a child intent. A step waits on a product question when the plan says it waits on an area of concern in the spec, or when "What to build" cannot be written without deciding what the product does. A question about how to build something is an unknown, not a product question, and is handled by R10.

### R7: When a step gets no task, the skill cuts no task for that plan

It says what has to be on `main` first: the child intent, with this intent as its parent, and the plan's step saying `- intent: <child>`. This follows what C1 proposes.

### R8: Every task has a size of 1, 2, 3, 5 or 8

Each size means what the intent's table says. The skill carries that table word for word.

### R9: A step that would be bigger than one 8 is split into tasks cut from that step

Every piece has the step's number as its `step`. Before cutting a 5 or an 8 the skill tries to split it, and the pull request says, for each 5 and each 8, why it was not split.

### R10: When unknowns dominate a step, the unknown sits in one task and the rest of the step waits for it

That task is a spike or the first slice of the work. A spike's "Done when" is the question answered in writing. With a first slice, the other pieces are cut in the same pull request and depend on it. With a spike, the other pieces are cut and sized after the spike is done, as C2 proposes.

### R11: A task of size 8 says it gets a plan of its own

Its "What to build" says the task's first commit is its own plan, started with `asdlc plan new <slug>/<task>`, and its "Done when" has that plan as a criterion.

### R12: A task names another under `depends` when it needs what that one builds, and for no other reason

Two tasks that change the same file do not depend on each other for that reason. A task with no `depends` can start as soon as it is on `main`.

### R13: The pull request gives, for each size, a reason in complexity, unknowns and risk, and none in time

No hours, days or weeks, in the pull request or in a task.

### R14: A task's "What to build" and "Done when" are enough for someone who never saw the conversation to start, and to review

"What to build" names the files, the functions and the plan's step. Each line of "Done when" is one a reviewer can answer yes or no to.

### R15: The pull request's description accounts for every step of the plan

One line for each step: the task or tasks cut from it, with their sizes, or what it waits for.

### R16: `asdlc document check` is clean on the tasks the skill wrote

### R17: The tasks branch changes no file but the new `task.md` files

A task that is already on `main` is not changed, and so its size is not changed. Asked to resize one, the skill says a size records what was known when the task was accepted, and changes nothing.

### R18: The skill shows the draft and applies corrections before anything is pushed

The draft is every task's body, and the line for each step that R15 asks for.

### R19: The skill opens a pull request and never merges it

### R20: The skill has an eval case where it must act and one where it must stay out

`just check` already fails without them.

## Design

### The skill

`plugins/asdlc/skills/generating-tasks/SKILL.md` (new) (R1). It is a skill for the reason the first three are: the tasks are written with the person who will accept them. It follows `plugins/asdlc/skills/generating-a-plan/SKILL.md` step for step, so the four skills read alike.

With the skill loaded, Claude works in this order:

1. Read `intent/<slug>/intent.md`, `spec.md` and `plan.md` as they are on `main`, and the files the plan lists. When the plan is not on `main`, say which merge the tasks wait for and stop (R3). Reading comes first here, where the other skills run their command first, because `asdlc task new` needs a step, a size and what the task depends on before it can be run.
2. Go through the steps in order and decide, for each:
   - whether it waits on an open product question (R6). If any step does, say which, say what has to be merged, and stop without cutting anything (R7);
   - its size, from the intent's table (R8), by complexity, unknowns and risk (R13);
   - whether it is split: only when it is bigger than an 8, or a 5 or an 8 that comes apart cleanly, or when unknowns dominate it (R5, R9, R10);
   - what it needs that another task builds (R12). The skill reads the plan's "Files that change" and each step's text to see what overlaps. That is best effort. A shared file alone is not a dependency, and no list of files is written on a task.
3. Run `asdlc task new <slug>/<nn>-<name> --step <n> --size <s> --depends <task> --title <title>` once for each task (R2). `<nn>` counts the tasks in the order they would be built, as the seven on `main` do. The first run makes `tasks/<slug>`.
4. Write each task's body: "What to build" and "Done when" (R14), and for an 8 the plan of its own (R11). Leave the frontmatter alone.
5. Run `asdlc document check <slug>` and fix what it prints (R16).
6. Show the draft: every task, and the line for each step (R15, R18). Apply what the person corrects.
7. Commit the `task.md` files alone, with the subject `Tasks: <the intent's title>`. Run `asdlc branch check` (R17). Push, open the pull request with the line for each step and the reason for each size in its description (R13, R15), and stop (R19).

A split step's pieces all carry the step's whole `delivers` list, because `asdlc task new` copies it and the skill does not edit frontmatter. That is right as the code stands: `_progress` in `src/asdlc/domain/requirements.py` calls a requirement built only when every task that delivers it is done.

Steps 2 and 3 follow what C1 and C2 propose. If their owner decides otherwise, the design changes there, and R7 and R10 are the requirements to revisit.

### What the command already does

Nothing in `src/asdlc` changes. Read in `src/asdlc/cli.py`, `src/asdlc/domain/guard.py`, `src/asdlc/domain/lint.py` and `src/asdlc/domain/documents.py`:

- `task new <slug>/<task> --step <n>` switches to `tasks/<slug>`, making it from `main`, and refuses with "intent/<slug>/plan.md is not on main yet" when the plan is not merged (R3).
- It writes `intent/<slug>/tasks/<task>/task.md` from `src/asdlc/templates/task.md`, with `step`, `delivers` copied from the step, and `depends` and `size` from its flags (R2). It refuses a step the plan does not have, and a task that already exists.
- The guard allows `tasks/<slug>` to change only `intent/<slug>/tasks/<task>/task.md` (R17). It does not allow `plan.md`, a task's own `plan.md`, or another intent's files.
- Lint's `step` rule finds a task cut from a step the plan does not have, `delivers` one that delivers a requirement no spec has, and `depends` one that depends on something that is not another task of the intent.
- Lint's `coverage` rule: once a plan has any task, every step needs a task or a `- intent: <child>` line. Several tasks may share one step, so a split needs nothing new (R9).
- Lint's `child` rule: a step's `- intent: <child>` needs that intent to exist and to name this one as its parent. `asdlc intent new <child> --parent <slug>` writes that.

Lint does not read `size`: the key is optional and takes any value. That stays, and so do the seven tasks on `main`. R8 is the skill's to do and an eval pattern's to check (C5).

### The eval cases

Four cases under `plugins/asdlc/evals/` (each a new `case.yaml` and `scaffold.sh`), in the format the plan skill's cases use. Each scaffold builds a repository with its documents already in git, so graders open the files under `intent/<slug>/tasks/` by path.

- `tasks-from-an-accepted-plan` acts. `main` holds an intent, its spec and a plan of three small steps, where the third needs what the first builds and the second stands alone. Patterns check that `asdlc task new` ran, that only `task.md` files were created (R2, R17), that each of the three steps is some task's `step` and no step has two tasks (R4, R5), that every `size` is 1, 2, 3, 5 or 8 (R8), that the third step's task has `depends` naming the first step's task and the second step's task has no `depends` (R12), that no placeholder from the template is left (R16), that no task speaks of hours, days or weeks (R13), and that nothing was pushed. A judge checks R14.
- `tasks-with-a-step-to-split` acts. One step of the plan holds an unknown the rest of that step rests on. Patterns check that more than one task has that step as its `step` or the one task cut from it is named as a spike, and that every other task cut from that step depends on the first (R9, R10). A judge checks that the unknown sits in one task.
- `tasks-with-an-open-question` stays out. One step of the plan says it waits on `C1` in the spec. Patterns check that no `task.md` was created, and that the answer names the step and says a child intent is needed (R6, R7).
- `tasks-wait-for-the-merge` stays out. The plan is on the branch `plan/<slug>` and not on `main`. Patterns check that no `task.md` was created, that no `tasks/` branch was made by hand, that Claude merged nothing, and that the answer says the plan has to be merged first (R3).

`tests/test_evals.py` needs no change: it already finds every skill and case, and lints what each scaffold builds. `README.md` gains the skill in its table, and loses the line that says cutting tasks is done by hand.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The task format and its lint stay as they are today. | No requirement changes them. Nothing under `src/asdlc` changes. C5 says what that leaves unchecked. |
| `asdlc task new` keeps working as it does today. | R2 uses it as it is. A split step needs no new flag. |
| The guard on the tasks branch keeps working as it does today. | R17. The guard is not changed, which is why R7 and R11 are written as they are (C1, C4). |
| The seven tasks already on `main` stay valid. | Nothing in the format or in lint changes, and R17: the skill changes no task on `main`. |
| A skill lands with an eval case where it acts and one where it stays out. | R20. |
| The skill never merges. | R19. The skill stops once the pull request is open. |
| The work stays as close as it can to Anthropic's AI-native SDLC course, whose lesson on parallel sessions says "The engineer splits the work into tasks that touch different files, using the plan from the plan mode play (Stage 3: Build) to see where the work is independent.", "Tasks that share files run in a single session, one after another." and "Each parallel task gets its own worktree", and whose lesson on plan mode says "With a solid plan, the implementation is often a single pass." | Met in part. The plan is what the skill reads to see where the work is independent (R12), and a task with no `depends` can be built in a worktree of its own. Not met for "Tasks that share files run in a single session, one after another": the requester decided in Q1 that two tasks may change the same file. A single pass is not one task (R4), decided in Q2. C3 says what the departure costs. |
| A step that still has open product questions becomes a child intent, not a task. | R6 and R7. The skill cuts no task for it and says a child intent is needed. It does not write the child intent itself (C1). |
| A step that is specified becomes a task. | R4. |
| A step that is specified but large also gets a plan of its own. | R11. Large is an 8 that could not be split, by the requester's answer to Q3. The task says it gets a plan. The plan itself is written when the task is built (C4). |
| Size is by complexity, unknowns and risk, never by time. | R13. |
| A task's size is 1, 2, 3, 5 or 8 story points, and each size means what the table under this list says. | R8. |
| An 8 is the largest task. Anything that feels bigger is not a task yet and is broken down. | R9. |
| When unknowns dominate the estimate, a spike comes first and the work is sized after it. | R10, with the cost in C2: the work after a spike is cut in a second pull request. |
| A task is split so that the unknown sits in one piece, either a spike or the first slice. The other pieces can then be sized with confidence. | R10. |
| A size is not changed once its task is accepted. It records what was known at the time, and what was learned goes into the next sizing. | R17. |

## Open questions from intent

### Q1: The course has the engineer split by which files each piece touches. Our plans are split into steps, and a task is cut from one step. What should happen when two steps touch the same file, or when one step holds work that is independent?
- answer: answered

From the requester, when the spec was asked for. A file is not limited to one task. Two tasks may change the same file, and a conflict is resolved on the branch that merges second, the way developers normally would. A task is cut from a step, and depends on another only when it needs what that one builds (R12). The skill reads the plan to see what overlaps, as best effort: there is no list of files on a step or on a task, and no lint rule. Resolving a conflict is the worker's job, and the worker is a later intent. Independent work inside one step stays in that step's task (R5). The requester chose this knowing it departs from the course's line that tasks sharing files run one after another.

### Q2: Should a plan that is a single pass become one task, or still one task for each step?
- answer: answered

From the requester. Still one task for each step. A single-pass plan is not collapsed into one task, and a plan with one step gives one task. A step gives more than one task only when it is too big for one and is split, as the intent's sizing rules say (R4, R5).

### Q3: Where is the line between a task that is large and gets a plan of its own, and a step that should have been a child intent?
- answer: answered

From the requester. A step with an open product question becomes a child intent (R6). Anything else is a task. An 8 is split when it can be, and an 8 that cannot be split also gets a plan of its own (R9, R11).

## Areas of concern

### C1: One step with an open product question holds up every task of the plan
- owner: Bruk Habtu

Four things the intent asks for cannot all hold in one pull request. A step with an open product question becomes a child intent and not a task. Lint is clean on the pull request. The guard on the tasks branch and the lint stay as they are. A person asks for the tasks and gets a pull request.

Lint's `coverage` rule fails a plan as soon as it has one task and a step with neither a task nor `- intent: <child>`. The `child` rule needs that child intent to exist with this intent as its parent. On `tasks/<slug>` the guard allows `task.md` files only, so the skill can add neither the child intent nor the line in the plan. Cutting the other steps' tasks and leaving the step out gives a pull request that fails lint.

Proposed, and what R7 assumes: the skill cuts nothing. It names the step and says what has to be merged first: the child intent, captured on `intent/<child>` with `asdlc intent new <child> --parent <slug>`, and the plan's step changed to say `- intent: <child>` on `plan/<slug>`. The person asks for the tasks again after those two merges. The cost is that the first outcome is not met for such a plan until two more pull requests are merged.

The other ways through are to let the pull request fail lint until the child intent lands, or to change the guard or the `coverage` rule. Each breaks something the intent says to keep.

The skill does not write the child intent. It belongs to the `capturing-intent` skill, in the requester's words.

### C2: After a spike, the rest of the step's tasks need a second pull request
- owner: Bruk Habtu

The intent says a spike comes first and the work is sized after it, and that a size is not changed once its task is accepted. So the work behind a spike cannot be in the same pull request with a size on it.

Proposed, and what R10 assumes: the spike is the only task cut from that step, which satisfies lint's `coverage` rule. Its "What to build" says the rest of the step is cut once it is done. The person then asks for the tasks again, and the skill adds them on `tasks/<slug>` in a second pull request. A task of another step that needs what the uncut work builds waits for that second pull request too.

Three things follow that nobody has decided. Between the spike's merge and the second pull request, `asdlc requirement list` shows the step's requirements as built, because the spike is the only task that delivers them. A local `tasks/<slug>` left from the first pull request is behind `main`, and `asdlc task new` switches to it as it is. And the outcome "holding the tasks for that plan" is met in two parts.

### C3: Two tasks built at the same time can change the same file, and nothing says so
- owner: Bruk Habtu

Decided by the requester in Q1, and written here for its cost. The course has tasks that share files run one after another. Here they may run at once, the second to merge resolves the conflict, and no task and no lint rule records the overlap. The skill's reading of the plan for overlap is best effort. Until the worker intent says how a worker resolves a conflict, a person does it.

### C4: A task of size 8 says it gets a plan of its own, and nothing checks that it does
- owner: Bruk Habtu

The guard does not let `tasks/<slug>` add `intent/<slug>/tasks/<task>/plan.md`, and `asdlc plan new <slug>/<task>` works on `task/<slug>/<task>`, which waits for the task's merge. So the plan cannot be in the tasks pull request. R11 puts it in the task's "Done when". The task format has no key for it and stays as it is, and the guard does not judge that a plan was committed before the code. Whoever reviews the task's pull request is the only check.

### C5: Only the skill holds a size to 1, 2, 3, 5 or 8, and keeps an accepted size from changing
- owner: Bruk Habtu

Lint does not read `size`, and the intent keeps lint as it is. The guard lets `tasks/<slug>` change a `task.md` that is already on `main`. A task written by hand, or by a session that did not load the skill, can have a size of 13 or none, or a new size on an accepted task, and lint and the guard are clean.

### C6: An eval run is one turn with no network, and two requirements rest on a judge
- owner: Bruk Habtu

No case shows a correction being applied (R18) or a pull request being opened (R19), so no case reads the description R13 and R15 ask for. As with the first three skills, those are shown by using the skill in a live session on this repository's next plan. R14, and whether an unknown sits in one task (R10), need a judge, and a judge's verdict varies between runs. No case rests on a judge alone.
