# Intent: the loop should be quick and run on git alone

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-10-21

## Problem

"This process is quite slow - our intents are small so we go through many of these loops." Every intent goes through four pull requests (intent, spec, plan, change), and each one stops the work until I read and merge it. The three intents waiting now would take nine more pull requests before any of them changes what the plugin does. The stops aren't only a problem for small work: a large project goes through the same four, once for every piece.

"We should be GitHub agnostic. This would be really painful if we wanted to work on something locally." Today a gate is defined as a pull request merge, the skills open pull requests, and the review only runs in GitHub Actions, through a plugin that reads the change with `gh`. Without GitHub, the loop has no gates and no review.

I'm trying to support a model where multiple engineers, each on their own machine with their own setup, have multiple agents running. Nothing today lets one agent claim a piece of work so that no other agent, on that machine or another, starts it too.

## Proposed outcome

- Work of any size gets from an accepted intent to a merged change with fewer stops than today. A stop happens only where a person's decision changes what gets built.
- The plan is still approved before any file is edited, and every gate is still a recorded human action.
- The whole loop (capturing an intent, writing the spec and plan, the checks, the review, and working out what comes next) runs in a local clone with git and the plugin's own scripts, with no GitHub account and no network.
- On GitHub, the same steps run automatically from Actions by calling the same scripts, with no logic of their own.
- Claude cannot pass a gate itself, locally or on GitHub.
- An agent can claim a piece of work, and no other agent on any engineer's machine can then start it.
- The board's own changes are committed and pushed automatically, so every engineer's agents see the same state.

## Affected users and systems

- Me, as the person who passes every gate.
- The plugin's skills, scripts, hooks and workflows.
- The plugin's spec, whose design has a pull request as each gate.
- Anyone who installs the plugin and works locally or without GitHub.
- Teams where several engineers each run several agents on their own machines.

## Constraints

- A change still cannot alter the checks or evals that judge it (spec R23), locally or on GitHub.
- The review never approves; a person merges.
- The board's own commits and pushes don't go through any hooks.
- The released version must not edit itself (spec R21).

## Open questions

- [ ] I want to explore going back to Backlog.md, which keeps tasks, drafts, decisions and documents as files in git, and which I think works for large projects too. Should the loop's artefacts and gates live on a Backlog.md board instead of in `intent/`, `spec/` and `plan/` files?
- [ ] If so, does the plugin require Backlog.md, or support it alongside plain files for repositories that don't use it?
- [ ] How does an agent claim a task, and what happens when two agents on different machines try to claim the same one at once?
- [ ] If the board's commits skip hooks, what stops an agent from passing a gate through a board change?
- [ ] What decides where a stop is needed, and who applies that rule?
- [ ] When the plan is approved in the session rather than by a merge, how is that approval recorded in git?
- [ ] Locally, how does the history show that a merge into `main` was made by the person and not by Claude?
- [ ] Locally, where does the review's output go, so the person sees it before merging?
- [ ] Locally, what starts the next stage after a gate: the next session, a git hook, or a command the person runs?
- [ ] Should the small-changes intent (`intent/small-changes.md`) be settled by the same spec?
