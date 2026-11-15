# Intent: an intent can be closed

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

"A part of me also wonders if intents should be saved as a document like a spec once accepted? Or to avoid putting them as a task at all. Not sure."

An intent is a task on the board because that is what lets it be accepted, be the parent of the work, and carry the outcomes the work has to reach. But it is an odd task. Nobody claims it. It sits in To Do for as long as its children take, beside work that can actually be picked. Its acceptance criteria are not things a worker does: they are what must be true when everything under it is finished.

And asdlc stops at the last child. Nothing says who checks the intent's outcomes against what was built, when it becomes Done, or what happens when every child is Done and an outcome still is not met. Nothing stops its text changing after a person accepted it, either, so the finish line the children were planned against can move without anyone seeing it move.

I am not sure an intent should stay a task. I am sure that, whatever it is, it needs an end, and its accepted text needs to hold still.

## Proposed outcome

- When the work under an intent is finished, a person is asked to judge each of its outcomes against what was built, and the intent closes only when they have.
- An outcome that is not met when every child is Done becomes new work under the intent, not a closed intent with a gap.
- The intent's problem, constraints and outcomes do not change after acceptance without that change being visible on the board as a change to accepted work, with who made it and why.
- An accepted intent does not look like work waiting to be picked, on the board or in `asdlc next`.
- A person can see, for an intent, which outcomes are met so far and which children deliver them.

## Affected users and systems

- The person who wrote the intent, who is the one able to say whether it was met, and the engineer and orchestrator working under it.
- `asdlc accept`, `asdlc next`, `asdlc mine`, the board guard, and the capture-intent and orchestrate skills.
- `asdlc stats`, whose plan-stage numbers follow an intent from draft to acceptance and no further.

## Constraints

- Closing an intent is a person's, as accepting it is. The board guard refuses it from agents and says why.
- The children still hang off the intent, and accepting an intent still accepts its drafts in one board change.
- This repository keeps its own intents as files accepted by merging a pull request; that route keeps working.
- A change that weakens what an accepted intent asked for is never made quietly to let it close.

## Open questions

- [ ] Should an accepted intent stay a task, become a document with the task kept only as the parent and the gate, or be a document alone? What would each lose: the status change at acceptance, the parent of the children, the outcomes that get checked?
- [ ] What tells the orchestrator the work under an intent is finished: every child Done, every release closed, or a person saying so?
- [ ] Who is asked to judge the outcomes when the person who wrote the intent is not the engineer running the board?
- [ ] How is a change to an accepted intent made at all: refused outright, or allowed through a command that records it and marks the finish line as moved?
- [ ] Does a status of its own, or a label, keep an accepted intent out of the columns where pickable work sits?
- [ ] Should `asdlc stats` report from acceptance to close, and how often an intent closed with an outcome reworded?
