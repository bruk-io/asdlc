# Intent: a clear rule for which changes can skip the loop

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-10-20

## Problem

A typo or a one-line fix shouldn't need an intent, a spec and a plan. But this repository's CLAUDE.md says nothing changes except through the loop, so today even the smallest fix is either blocked on three pull requests or made against the rule. I want a clear rule for which changes can skip the loop and go straight to a pull request, without that becoming a way around the loop.

## Proposed outcome

- A written rule says which changes may go straight to a pull request without an intent, a spec and a plan. A contributor, or Claude, can apply it to a given change and get the same answer a reviewer would.
- A typo or a one-line fix that meets the rule needs only its own pull request, and a person still merges it.
- The rule has no judgement call that the author of a change can settle in their own favour. A change that does not clearly meet it goes through the loop.
- Splitting a larger change into several small ones does not get it past the rule.
- CLAUDE.md no longer says that nothing changes except through the loop without also stating the exception, so the two do not contradict.
- Whether a pull request used the exception is visible on the pull request, so a reviewer can reject it and send it through the loop.

## Affected users and systems

- Whoever opens pull requests against this repository, whether a person or Claude.
- The person who reviews and merges them.
- This repository's CLAUDE.md, and the plugin's own loop as described in its spec.

## Constraints

- The loop stays the only way for anything that changes what the plugin does, or how its changes are judged. The exception must not become a route to alter behaviour, checks or tests without review of the intent.
- A change cannot alter the checks or evals that judge it, and a person merges every change. Neither is relaxed for small changes.
- The released version must not edit itself (spec R21).

## Open questions

- [ ] What counts as small: a number of lines or files, a kind of change (typos, wording, formatting, broken links), or both?
- [ ] Are there files where no change is small, such as scripts, hooks, tests, skills, the artefact templates, or the intent, spec and plan files themselves?
- [ ] Is a one-line fix to behaviour (code that runs) eligible, or only changes that cannot alter what the plugin does?
- [ ] Who decides that a change qualifies, and what stops the author from deciding in their own favour: a check in `./scripts/check`, a label or a line in the pull request description, or the reviewer alone?
- [ ] What happens when a reviewer finds that an exempt pull request was not small after all: is it closed and restarted as an intent, or can it be converted?
- [ ] Should the use of the exception be counted over time, so that a rising share of exempt changes shows the rule leaking?
- [ ] Where is the rule written so that it cannot be missed: CLAUDE.md, the plugin's spec, or both?
