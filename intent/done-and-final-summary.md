# Intent: tasks use Definition of Done and the final summary

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

"Backlog.md has the following for tasks: definition of done, implementation plan and implementation notes. Obviously we are using the acceptance criteria already." "Tasks have a definition of done, a plan and so on. It's likely worth using that."

asdlc uses three of a task's sections and leaves two empty. Acceptance criteria say what a task delivers, the plan is what a person approves, and the notes hold the checks `asdlc record-check` appends. Definition of Done and the final summary are never written.

What they would hold is on the board anyway, in the wrong places. What must be true of every task (the repository's check passed on the last commit, the change cites the requirements it delivers) is spread over rules, the review policy and each reviewer's reading, so it is restated per project and checked by judgement. And the worker's own account of what it built goes into the notes with `asdlc finish`, mixed in with check output, so reading a finished task means reading past its evidence log to find out what happened.

I want each of a task's sections to hold the one thing it is for.

## Proposed outcome

- What every task in a project must satisfy is written once for the project, appears on each task as its Definition of Done, and is not repeated in each task's acceptance criteria.
- Each Definition of Done item is something a reviewer can verify from the task and the change, and the review says which were not met.
- Where a program can tell whether an item holds, `asdlc` checks it when the worker hands the task over, and refuses with the reason when it does not hold.
- A finished task's final summary says what was built, in the worker's words, and its notes hold the evidence. Each can be read without the other.
- A task made before this, and a board with no Definition of Done set, work as they do today.

## Affected users and systems

- Workers, who meet the Definition of Done and write the summary; reviewers, who judge against it; the engineer, who sets it and reads finished tasks.
- `asdlc init-board`, `asdlc finish` and `asdlc record-check`, the worker and reviewer agents, the team's review policy, and the break-down-intent skill.
- `asdlc stats`, which reads checks and reports out of a task's notes.

## Constraints

- A ticked box is not evidence. A Definition of Done item that only a worker's say-so supports is not allowed to stand in for a recorded check.
- Nobody edits `backlog/` by hand, including to set a project's defaults.
- Skills and agents are steering paths: a change to them passes the eval gate (spec R23).
- The numbers `asdlc stats` computes from notes keep their meaning.

## Open questions

- [ ] Who ticks a Definition of Done item: the worker when it claims it holds, the reviewer when it verifies it, or `asdlc` when it has checked it?
- [ ] Does asdlc ship a default Definition of Done with a new board, or is the list always the team's own?
- [ ] Can a project's defaults be set through Backlog.md's CLI, or only by a change to its config file that asdlc must make?
- [ ] Do a repository's own items add to the team's, as its review policy adds to the team's review policy?
- [ ] Which of today's review passes (evidence, size and approval) become Definition of Done items, and which stay the reviewer's judgement?
- [ ] Does `asdlc finish` move the worker's report from notes to the final summary, and what happens to the reports already in notes that `asdlc stats` reads?
