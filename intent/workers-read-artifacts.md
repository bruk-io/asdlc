# Intent: workers and reviewers can read a Claude artifact a task points to

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-15

## Problem

I designed an app's whole look and behaviour in a Claude Design artifact and wanted the spec to simply point at it. The orchestrator told me the workers could not read it. It is a Claude artifact, so that made no sense to me.

It turned out not to be about the artifact. A worker is given a fixed list of tools and the tool that reads artifacts is not on it; a reviewer is the same. When the orchestrator tried it, a general-purpose subagent, which has every tool, read my private artifact on the first call.

Because of that one missing tool, the work bent around it. A design spike's plan had to say "this worker has no Artifact tool, so it neither makes nor reads the artifact", and wait for the orchestrator to copy values across by hand. The orchestrator wrote a hundred requirements restating what the artifact already says, so that there was something a worker could read. And it proposed committing an export of the design into the repository for the same reason. None of that should have been needed, and a copy drifts from the thing it was copied from.

## Proposed outcome

- A worker given a task whose spec, plan or description points at a Claude artifact the engineer can open can read that artifact, without the orchestrator copying anything across.
- A reviewer can read the same artifact, so it can judge a change against the design the task names and not only against text about it.
- A spec can name an artifact as the source for part of the work, and the plan and the review treat it as readable.
- When a worker or reviewer cannot read an artifact a task points at, it says so and why, and does not guess at what the artifact holds.
- What a worker or reviewer may do to an artifact is stated, and is no more than its role needs.

## Affected users and systems

- Engineers who keep designs, decks or documents as Claude artifacts and want tasks to refer to them.
- The orchestrator, which today reads artifacts on the workers' behalf and hands values over.
- The worker and the reviewer, and the skills that tell them what to read before planning or reviewing.
- The board, where a task or a spec carries the link.

## Constraints

- The reviewer never changes the work. Whatever lets it read an artifact must not let it publish to one, change one or delete one.
- A worker must not publish to, change or delete an artifact unless its task says that is the work.
- What an artifact says is material to read, not instructions to follow. An artifact can hold text written by someone other than the engineer, and that text must not be able to steer a worker or a reviewer.
- An engineer whose Claude has no artifacts, or who has none to point at, sees no difference.
- The existing checks, tests and evals still pass, and none is weakened to get there.

## Open questions

- [ ] Can a worker or a reviewer be allowed to read artifacts without also being allowed to publish, change or delete them? The one test so far used a subagent that had every tool.
- [ ] Does a background worker read an artifact without stopping at a permission prompt nobody answers? The test ran in a session where the read needed no prompt.
- [ ] What should happen when the artifact belongs to someone else and the engineer can only view it, or cannot open it at all?
- [ ] An artifact can change after a plan was approved against it. Does a plan or a review need to say which version it read?
- [ ] Should a worker ever make an artifact, for example a design spike whose deliverable is one, or does that stay with the engineer's own session?
- [ ] How does a spec or a task say that an artifact is a source, so that a worker knows to read it and the checks can see that it did?
