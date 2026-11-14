# Intent: the code and the board can live in the same place

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

"Can we fix asdlc to allow for the code and the board to live in the same place." For a project with one repository, I want the board in that repository, not a second repository to create and keep beside it.

The first project set up this way (steg) showed that asdlc only half allows it. Registering the repository was refused until [the register change](../plan/board-in-the-code-repository.md), which let its work be picked, claimed and reviewed. What is left is what the agents working in that repository are given and held to:

- The team's rules never reach them. The rule loader treats a repository with a `backlog/` folder as a board and nothing else, so a file touched there gets no rules, from the team plugin or from the repository's own. The project worked around it by keeping its rules in its own `.claude/rules/`, which is exactly the agent setup in code repositories that the tasks repository is meant to replace.
- Nothing keeps their edits inside a claimed task's worktree, and nothing refuses a push to the default branch. The board guard gives a repository that is a board the board's rules only, so the rails that keep two workers apart in every other code repository are missing in this one.
- `asdlc doctor` reports failures there that are not failures: a local board with no scaffolding fails on a missing marketplace and missing preferences that `init-board --local` deliberately leaves out.

So a repository that holds its own board is the least protected place to run asdlc, when for one person with one project it is the simplest.

## Proposed outcome

- An agent that reads or edits a file in a repository that holds its own board gets the same team rules and repository rules it would get if the board were in a repository of its own.
- In such a repository an agent can change code only inside a claimed task's worktree, as in any other code repository with a board.
- An agent's push to that repository's default branch, and any force push there, is refused as it is elsewhere, while asdlc's own board changes still reach `origin/main` on a shared board.
- An agent still cannot edit `backlog/` by hand there, in the main checkout or in a task's worktree.
- A person can still commit and push to that repository themselves: the board's files, the team plugin and the project's own files.
- `asdlc doctor` passes on a repository that holds its own board and is set up as asdlc's own commands leave it, in both board modes, and fails only on something a person should fix.
- The guide says how to set up a repository that holds its own board from nothing to the first picked task, in one place.

## Affected users and systems

- Anyone running asdlc on a single repository, and the workers and reviewers their orchestrator launches there.
- The rule loader and the board guard (`hooks/`), `asdlc doctor` and `asdlc init-board` (`scripts/asdlc`), and the guide.
- The eval suite, which has no fixture with the board and the code in one repository.

## Constraints

- A board in a repository of its own keeps working exactly as it does today.
- The hooks are steering paths: a change to them passes the eval gate, and cannot ship in the same pull request as a change to the eval suite that judges it (spec R23).
- No check is weakened to make the same-repository case pass. Where the guard cannot tell what a command does, it still allows it and says so.
- A hook says why it denied something, and never fails silently.

## Open questions

- [ ] A task's worktree in such a repository carries its own copy of `backlog/`. Should that copy be hidden from the agent, ignored, or left as it is, given the board's rules already refuse edits to it?
- [ ] On a shared board beside the code, asdlc refuses to work while the main checkout has uncommitted changes. Is that right for a repository where a person also edits files, or should only changes under `backlog/` count?
- [ ] Does a repository that holds its own board carry the team plugin and marketplace at all, or are its rules simply the repository's own? `init-board --local` leaves them out, and `init-board` on the same folder adds them and makes the board shared.
- [ ] Should `init-board` notice that the folder already holds code and say which mode it is setting up, since today the same folder can be made local or shared by which flag was typed?
- [ ] Which eval cases need a same-repository fixture, and do they ship before the hook change, as R23 requires?
- [ ] Should a person's own session in that repository be guarded as an agent's is, or is there a way to tell the two apart that does not weaken the guard?
