---
kind: intent
author: Bruk Habtu
---
# Intent: Tasks for an accepted plan, as a pull request

## Problem

Once a plan is accepted in this repository, nothing turns it into tasks. For the last three intents (capture-intent, generate-spec, generate-plan) all seven `task.md` files were written by hand from the plan's steps. `asdlc task new` makes the file and copies what the step delivers, but everything that takes judgment is done by hand each time, with no stated rule: which steps become a task, whether a step is split, how big each task is, which task waits for which, and what goes under "What to build" and "Done when". Nothing judges the result either.

Intents, specs and plans are each done by a skill now. The split and the task generation need to be done the same way.

## Proposed outcome

- When a plan is on `main`, a person asks for its tasks and gets a pull request on the intent's tasks branch, holding the tasks for that plan, that they can merge or close.
- The pull request can be judged by reading it:
  - every step of the plan is accounted for
  - each task says enough that someone who never saw the conversation could start
  - each task has a size
  - tasks that cannot be built at the same time say which one waits
- The person can merge the pull request without rewriting a task.
- Lint is clean on the pull request.
- This is a skill in the plugin, like the other three.

## Affected users and systems

- The person who asks for the tasks and merges them.
- Whoever builds a task later, a person or a worker agent in a worktree of its own, because the task is all they are given.
- Whoever reviews a task's pull request against it.
- The task format and its lint, `asdlc task new`, the guard on the tasks branch, and the plugin's skills and their eval cases.

## Constraints

- The task format and its lint stay as they are today.
- `asdlc task new` keeps working as it does today.
- The guard on the tasks branch keeps working as it does today.
- The seven tasks already on `main` stay valid.
- A skill lands with an eval case where it acts and one where it stays out.
- The skill never merges.
- The work stays as close as it can to Anthropic's AI-native SDLC course, whose lesson on parallel sessions says "The engineer splits the work into tasks that touch different files, using the plan from the plan mode play (Stage 3: Build) to see where the work is independent.", "Tasks that share files run in a single session, one after another." and "Each parallel task gets its own worktree", and whose lesson on plan mode says "With a solid plan, the implementation is often a single pass."
- A step that still has open product questions becomes a child intent, not a task.
- A step that is specified becomes a task.
- A step that is specified but large also gets a plan of its own.
- Size is by complexity, unknowns and risk, never by time.

## Open questions

### Q1: The course has the engineer split by which files each piece touches. Our plans are split into steps, and a task is cut from one step. What should happen when two steps touch the same file, or when one step holds work that is independent?

### Q2: Should a plan that is a single pass become one task, or still one task for each step?

### Q3: Where is the line between a task that is large and gets a plan of its own, and a step that should have been a child intent?
