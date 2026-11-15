# Intent: decisions are records on the board

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

"There is a backlog concept for decisions. Should we be updating the asdlc plugin to take advantage of that?" Backlog.md keeps decision records, each with a status, and asdlc doesn't use them at all.

The first project run through asdlc (steg) shows where decisions end up instead. Choices I made in conversation are written into the spec's prose ("decided on 2026-11-13"), so a settled choice reads the same as a proposal beside it. Four spikes each end with "a board document records the choice", which is a decision with nowhere proper to go. Nothing says who accepted a choice, and a worker building on one has no id to cite and no way to tell whether it still stands.

I want a choice that shapes the work to be its own record on the board: proposed by whoever worked it out, accepted by a person, and cited by the tasks that depend on it.

## Proposed outcome

- A design choice made for an intent is a decision record on the board, with its context, what was decided and what follows from it, and not a paragraph in the spec.
- A spike whose result is a choice delivers a proposed decision, linked on the spike's task.
- A decision is accepted by a person, in their own terminal, and the record says who and when. An agent can propose a decision and cannot accept one.
- A task that depends on a decision cites it, and its worker and its reviewer read it before they plan, build or judge.
- Work that depends on a decision still only proposed does not start as if it were settled.
- A decision that is replaced stays on the board, marked as replaced by the one that followed it, so the history of a choice can be read.
- The spec says which decisions shape it by citing them.

## Affected users and systems

- The engineer, who accepts decisions, and the orchestrator, workers and reviewers who propose and read them.
- The spec, breakdown and orchestrate skills, the worker and reviewer agents, the board guard, `scripts/asdlc`, and the guide.
- Boards that already hold decisions written into specs and documents, such as steg's.

## Constraints

- Every change to a decision goes through `asdlc`, committed and pushed like any other board change. Nobody edits `backlog/` by hand, and Backlog.md's own command can create a decision and change its status but cannot write its body.
- Accepting a decision is a person's, as accepting work and approving plans are. The board guard refuses it from agents and says why.
- Skills and hooks are steering paths: a change to them passes the eval gate, and cannot ship in the same pull request as a change to the eval suite that judges it (spec R23).
- A board with no decisions keeps working as it does today.

## Open questions

- [ ] Which choices need a decision record and which stay in a plan or a spec? A record for every small choice would bury the ones that matter.
- [ ] How is a decision linked to the work: on the intent, on each task that depends on it, or both? Backlog.md gives a task references and documentation, and neither is a typed link to a decision.
- [ ] Does "work that depends on a proposed decision does not start" mean `asdlc next` skips it, a claim refuses it, or the plan approval is where it is caught?
- [ ] Is a spike that ends in a decision still a task of type `spike`, or does design work get a type of its own?
- [ ] What statuses does a decision have beyond proposed and accepted: rejected, replaced? Backlog.md's status is free text.
- [ ] How do decisions already written into specs and documents on an existing board become records, and who accepts them after the fact?
- [ ] Does the wait between a decision being proposed and accepted belong in `asdlc stats`, as the other gates' waits do?
