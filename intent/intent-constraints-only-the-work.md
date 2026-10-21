# Intent: an intent's constraints are about the work, not the run that wrote it

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-10-20

## Problem

Every intent the capture-intent skill has written so far listed the instructions for its own run as constraints on the work. Both #6 (small changes) and #7 (session cost visibility) carried the pull request footer line ("Co-authored with the asdlc plugin, version 0"), and #6 also carried the repository's spelling convention. The trial run during the v0 build did the same. A spec has to settle every constraint, so each leaked line becomes a requirement with nothing to do with the problem. Today these lines are only caught when someone reads the intent closely, and #6 and #7 were merged with them and needed a follow-up fix (#14).

## Proposed outcome

- An intent written by the skill lists under Constraints only what must hold or must not break for the work itself.
- Instructions about how the run is carried out, such as pull request wording, commit conventions or house style, don't appear in the intent unless the requester states them as a constraint on the work.
- Constraints the requester does state still appear, in their words.
- A repeatable case built from #6 and #7 fails against the skill as it is today and passes once this is done, so the fault can't come back unnoticed.

## Affected users and systems

- Whoever asks for work and then accepts an intent by merging it.
- The capture-intent skill and the intent template.
- The spec stage, which reads Constraints and has to settle each one.

## Constraints

- The skill must not start dropping or rewording constraints the requester actually stated.
- The released version must not edit itself (spec R21), and the change cannot loosen the checks or evals that judge it (spec R23).

## Open questions

- [ ] Where did the leaked lines come from in each run: the prompt that started it, this repository's CLAUDE.md, or both?
- [ ] Is a repository convention, such as spelling, ever a constraint on the work, for example when the work is writing?
- [ ] Can a deterministic check catch this, or does it need a task eval with a model judge?
- [ ] Should the same rule apply to the spec and plan the plugin writes?
- [ ] Is #7's description naming a constraint the file never had the same fault, or a separate one?
