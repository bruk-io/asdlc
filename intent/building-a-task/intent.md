---
kind: intent
author: Bruk Habtu
---
# Intent: Build a ready task into a pull request

## Problem

Building a task is still done by hand in this repository. Intents, specs, plans and tasks are each produced by a skill now. Once a task is on `main`, nothing says how it gets built.

For the generate-tasks intent the three tasks were built by Claude in one long conversation: it made each branch with `asdlc branch new`, wrote the code, ran the checks, and opened each pull request, with nothing written down about how. A few things went wrong or were left to chance on the way:

- Nothing recorded when a task was started. `asdlc task list` shows a task as claimed only once its branch exists, and a branch made on one machine is not seen from another until it is pushed.
- Two tasks were built side by side and both changed one line of the README. When the second was merged the conflict was settled by taking one side, and the README was wrong until a later fix.
- One task changed its intent's plan. The guard marked it and asked for the reason in the pull request, and that reason is a paragraph on GitHub.

## Proposed outcome

- When a task is ready and a person asks for it to be built, they get a pull request for that task that they can merge or close.
- The person who asks can merge that pull request without redoing any of it.
- The work is done by something that was given the task and nothing else.
- The work is done in a worktree of its own, so several tasks can be built at once.
- `asdlc task list` shows the task in progress from when work on it starts, from another clone as well.
- The pull request shows the output of the repository's checks, as they were run.
- The change stays inside what the task allows.
- When the task's branch conflicts with `main`, the conflict is resolved on that branch.
- It never merges.
- It changes no document but the task's own plan, and the intent's plan when the work departs from it, in the same commit as the code. The guard already allows that and marks it.

## Affected users and systems

- The person who asks for a task to be built and merges it.
- Whoever reviews the pull request.
- Whatever is building another task at the same time.
- The guard.
- The state `asdlc task list` reads from git.
- CI.

## Constraints

- The guard for a task's branch does not break.
- The task states are read as they are read today.
- `asdlc branch new` does not break.
- The tasks already on `main` do not break.
- Anything Claude loads lands with an eval case where it acts and one where it stays out.
- It stays as close as it can to Anthropic's AI-native SDLC course.
- The course's lesson on parallel sessions says "Each parallel task gets its own worktree" and "Each independent session knows nothing about the others, and the engineer steering them is the only thing they share."
- The same lesson says "A subagent runs inside a single session as a scoped helper with its own context window and tool limits and suits jobs that recur in multiple tasks, such as verifying the app runs as expected."
- The course's lesson on the feedback loop says "Run the tests before reporting a task complete, and show the output.", "If a test fails, fix the code, not the test." and "An agent fixing code must not be able to weaken the check on that code."
- The course's lesson on plan mode says "When implementation departs from the plan, update `plan.md` in the same commit."
- Decided already, in the generate-tasks spec: two tasks may change the same file, and a conflict is resolved on the branch that merges second, the way developers normally would. Resolving it is the builder's job.
- A task of size 8 starts with a plan of its own, as the generate-tasks spec says.
- Starting several tasks at once and choosing which to start is not part of this. That is a later piece of work.

## Open questions

### Q1: Should a task be linked to a pull request to show when it is in progress?

### Q2: Should `asdlc task` give a way to create a branch and a pull request from the task?

### Q3: How does this work with claims? Does starting a task also push, and how does asdlc know about tasks started somewhere else?

### Q4: Is the builder a session of its own, a subagent, or a skill?

The course has parallel sessions do the building and keeps subagents for helpers such as a verifier.

### Q5: What does the builder do when the checks fail and it cannot fix them, or the task turns out bigger than its size?

### Q6: Who resolves a conflict that appears after the builder has finished, when its pull request is open and main has moved?
