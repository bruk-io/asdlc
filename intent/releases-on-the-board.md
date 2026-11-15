# Intent: a breakdown knows its releases

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

"We also don't seem to be using the backlog milestones? Is that intended?" It was not. Backlog.md has milestones, and asdlc never mentions them: not in the spec template, the breakdown skill, the picker or the numbers.

steg's spec split its requirements into three releases. The breakdown that followed put every child on the board with nothing saying which release it belonged to, until I asked. The milestones were then added by hand, each task assigned by hand, and a line written into the project's `CLAUDE.md` so the next session would keep doing it. `asdlc next` still knows nothing of them: it ranks by reservation, preferred repository and priority, so work for a later release can be picked while the first is unfinished. And the later releases were left unsplit on purpose, which the board could only record as two ordinary tasks titled "break the second release into tasks".

I want the releases a spec describes to be on the board, and the work to follow them.

## Proposed outcome

- When a spec divides its requirements into releases, each release is a milestone on the board, and each child task carries the milestone of the release it delivers.
- A breakdown that leaves a task with no release, when the spec has releases, is caught before a person is asked to accept it.
- Work for an earlier release is offered before work for a later one, unless a person says otherwise.
- A release that is deliberately not broken down yet is recorded as such, with what it waits for, and comes back as work when that is done.
- A person can see how far along each release is from the board.
- A spec with no releases, and a board with no milestones, work as they do today.

## Affected users and systems

- Whoever writes a spec with more than one release, the orchestrator that breaks it down, and the engineer who accepts it.
- The spec template, the write-spec and break-down-intent skills, `asdlc next`, and `asdlc stats`.
- Boards that already have milestones a person set by hand.

## Constraints

- A milestone never overrides a dependency: work whose dependencies are not Done is still not offered.
- Reserved work is still offered to its engineer first.
- Deciding what is in a release is the spec's, which a person approves. The breakdown follows it and does not move work between releases on its own.

## Open questions

- [ ] Are a spec's releases always Backlog.md milestones, or does a small spec with one release skip them?
- [ ] How does a milestone rank against priority and a preferred repository in `asdlc next`: before both, or only to break a tie?
- [ ] What records a release that is not broken down yet: a task of a type of its own, a milestone with a note, or the spec alone?
- [ ] Should `asdlc stats` report by release, such as time from the first claim to the last Done in each?
- [ ] Does accepting an intent accept every release at once, as today, or can a later release be accepted when it is broken down?
- [ ] Who closes a milestone, and does anything check that every requirement the spec gave that release was delivered?
