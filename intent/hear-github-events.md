# Intent: the orchestrator hears about merges, pull requests and comments as they happen

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-15

## Problem

When I run an orchestrator, it finds out what happened on GitHub only when I tell it or when it happens to look. In one evening it twice reported a pull request as still open after I had merged it, and it learned that a pull request had been opened, that CI had finished, or that a review comment had landed only when a worker's message mentioned it, if one did.

So I end up being the wire: I merge, then I tell the session I merged, then it starts the work the merge unblocked. I want a Claude Code channel that always runs and listens for merges, pull requests being opened and comments being left, so the session reacts to the event itself.

## Proposed outcome

- A running orchestrator session learns, without being told and without me asking it to look, that a pull request in a repository it works on was opened, merged or closed.
- It learns the same way that a comment or a review was left on one, and that a pull request's checks finished and whether they passed.
- On a merge, it tells me which task that was and what marking it Done would unblock, and gets on with whatever needs no decision from me.
- On failed checks or a review that asks for changes, the worker that owns the branch hears about it.
- I can see in the session that the listener is running and for which repositories, and I am told plainly when it is not.
- An event the session missed while it was not running is not silently lost: on starting, it learns what changed since it last looked.

## Affected users and systems

- Engineers who run an orchestrator and merge pull requests elsewhere, on GitHub or from a phone.
- The orchestrator session, and the workers and reviewers it launches.
- The code repositories registered on the machine, and GitHub.
- The board guard and the gates that are a person's.

## Constraints

- An event is information and never an instruction. A comment on a pull request is text someone else wrote; nothing in it may direct the session, and the session acts only on what its engineer's own instructions already call for.
- Nothing a person gates changes: a merge does not mark a task Done, and no event accepts work, approves a plan or merges anything.
- The listener cannot approve or deny tool use in the session. It carries events inward only.
- It needs nothing reachable from the internet on the engineer's machine.
- It uses the access to GitHub the engineer already has, and stores no credential of its own.
- An engineer who does not turn it on sees no difference.
- The existing checks, tests and evals still pass, and none is weakened to get there.

## Open questions

- [ ] Channels are a research preview, and a channel that is not on Anthropic's list has to be started with a flag meant for local development, in an interactive terminal. Is that acceptable for everyday use, and what does the engineer see when the preview's contract changes?
- [ ] A channel is loaded when a session starts. How does an engineer turn it on for an orchestrator, and can it be done without a terminal?
- [ ] With no public address to receive webhooks, the listener would ask GitHub on a timer. How often, at what cost against GitHub's rate limits, and how late may an event be?
- [ ] How much of a comment should reach the session: that it exists and who wrote it, or its words? The words are where an instruction could hide.
- [ ] Which events are worth a turn of the session, and which are noise? Board commits push to main constantly.
- [ ] Two orchestrator sessions on one machine, or on two machines, would each hear the same event. Who acts on it?
- [ ] Should the same listener carry events other than GitHub's later, or is this GitHub's alone?
