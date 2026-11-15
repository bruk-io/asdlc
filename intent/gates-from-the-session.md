# Intent: the engineer can accept work and approve plans from inside the Claude session

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-15

## Problem

Accepting work and approving plans are mine, and the board guard rightly refuses them when an agent tries. But the only way I have to do them is to run `asdlc accept` or `asdlc approve` in a terminal of my own. So whenever I work with an orchestrator I always need an actual terminal session running beside it, just to say yes.

That is worst when I am not at a terminal at all. I can follow a session from another device and read everything the orchestrator shows me, and then I cannot act on it. The orchestrator finishes a breakdown or gathers plans, tells me the command, and the work stops until I am back at a shell.

What I want is something only I can invoke from the session, such as a skill the model cannot call, for the things that are mine: accepting work, approving plans, and the like.

## Proposed outcome

- From inside a Claude session, I can accept an intent and its drafts with one thing I type, with no second terminal.
- From inside a Claude session, I can approve the plans I was shown, and an approval is still refused for a plan that changed after I saw it.
- An agent cannot invoke either one: not the orchestrator, not a worker, not a reviewer, and not because a message, a task or a document told it to.
- The board records the same thing it records today when I run the command in my own terminal, including that a person did it.
- The orchestrator tells me the thing to type in the session where it tells me the terminal command today.
- It works from wherever I can type into the session, not only at the machine the session runs on.

## Affected users and systems

- Engineers who run an orchestrator and are asked to accept work or approve plans.
- The orchestrator, whose skills tell the engineer what to run.
- The board guard, which decides what an agent may not do.
- The board's record of who accepted and who approved.

## Constraints

- The guard is not weakened. Everything it refuses an agent today, it still refuses.
- The gate stays a person's decision. Nothing an agent writes, and nothing in a task, a comment, a document or a message from another agent, can cause an acceptance or an approval.
- Running `asdlc accept` and `asdlc approve` in a terminal keeps working exactly as it does now.
- The existing checks, tests and evals still pass, and none is weakened to get there.

## Open questions

- [ ] Can a skill run the command itself when it loads, so that the model never makes the call, and does the guard then see nothing to refuse? This is untested.
- [ ] If the skill's body instead told the model to run the command, the guard could not tell that from an agent accepting work by itself. Is there any form of that which is safe, or is it ruled out?
- [ ] Typing `! asdlc accept <intent>` in the prompt already runs the command as the person. Does that work from every place a session can be followed, and is it enough to document it?
- [ ] Which gates does this cover besides accepting and approving: promoting a draft, archiving accepted work, marking a task Done, merging?
- [ ] Approving takes a digest for each plan. How does the person give those without retyping them, and without the orchestrator being able to choose them?
- [ ] Can an agent cause a person-only skill to run by any route, such as a scheduled prompt, a message from another session or a notification, and how is that shown not to happen?
