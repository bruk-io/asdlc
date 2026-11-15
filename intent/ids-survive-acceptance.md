# Intent: what cites a draft still points at it after acceptance

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

`asdlc accept` promotes an intent and every draft under it, and every one of them gets a new id: `DRAFT-1` became `TASK-1`, and `DRAFT-2` to `DRAFT-28` became `TASK-1.1` to `TASK-1.27`. asdlc re-parents the children and keeps their dependencies on each other, comments the old and new ids on the intent, and marks each task with the id it was accepted from.

It does not touch anything else that named a draft. On steg the spec's first line still read "DRAFT-1 until accepted" after the intent was accepted, and any document, description or note that cites a draft by id goes stale at the same moment. The skills warn about it ("refer to it by title as well as id", "keep no ids in this conversation"), which puts the burden on every writer to work around a renumbering only the tool knows about. Draft ids are also reused once a draft is promoted, so a stale citation does not just dangle: it can come to point at a different piece of work.

I want a reference written before acceptance to still be right after it.

## Proposed outcome

- After `asdlc accept`, every place on the board that cited one of the promoted drafts by id cites its task: task descriptions, notes and acceptance criteria, and the documents linked on the intent.
- The rewrite is part of the same board change as the acceptance, so there is no moment when the board is half renumbered.
- A citation of a draft that was not part of the acceptance is left alone.
- A draft id that is later reused cannot be confused with the task that once had it.
- The acceptance says what it rewrote, so a person can see it.

## Affected users and systems

- Whoever writes a spec, a contract or a breakdown before the intent is accepted, and every worker who reads them after.
- `asdlc accept` in `scripts/asdlc`, and the spec, breakdown and orchestrate skills, which carry the warnings.
- `asdlc stats`, which follows an intent across its acceptance.

## Constraints

- Accepting stays a person's command, one board commit, refused from agents.
- Text that only looks like a draft id is not rewritten: the rewrite must not change a document's meaning.
- The record of which draft a task was accepted from is kept.

## Open questions

- [ ] Could a draft and the task it becomes share one id, so nothing needs rewriting? Backlog.md assigns both, so is that asdlc's to change?
- [ ] Where can a draft id appear: only in the files under `backlog/`, or also in the team plugin and the code repository's own files?
- [ ] How is a real citation told from text that happens to match, such as a quoted command or a history of the renumbering itself?
- [ ] Should the old id stay visible beside the new one for a while, or is the comment on the intent enough?
- [ ] If nothing is rewritten, would refusing to cite a draft by id at all, in favour of a stable name, be the simpler rule?
