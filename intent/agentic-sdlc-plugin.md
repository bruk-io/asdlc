# Intent: an agentic SDLC plugin that builds itself

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-10-20

## Problem

I want my own agentic SDLC, built on Anthropic's AI-native SDLC playbook. I can't tell whether the harness I use over-constrains frontier models or matches current practice, because nothing measures whether each part still earns its place. As models improve, rules written for older models keep running with no signal that they have become dead weight.

## Proposed outcome

- A Claude Code plugin that implements the playbook's loop: all six stages (Plan, Design, Build, Test, Deploy, Maintain) and their twelve plays, each stage ending in a committed artefact that the next stage reads.
- The plugin builds itself. Every change to it starts as an intent in this repository and runs through its own loop.
- Every stage has evals with practical measures, and a new version of the plugin replaces the old one only when its evals hold.
- The plugin sheds parts that stop earning their place as models improve.

## Affected users and systems

- Whoever runs the loop, whether one person or a team.
- The repositories the plugin is installed in, starting with this one.
- Claude Code and the models it runs.

## Constraints

- New. Nothing is carried over from earlier plugins: no code, conventions or skills.
- No assumption about team size. Where the playbook expects a second person at a gate and there isn't one, something else stands in.
- Organisation-level parts of the playbook are in scope, even when one person runs the loop: approval hooks, managed settings, CI/CD and deployment, and closing the loop on metrics.
- Evals use practical measures. They prefer data that already exists (git history, CI runs, hook decisions, session transcripts) over new instrumentation, and deterministic checks over model judges.
- The loop cannot grade itself into passing. A change cannot alter the evals that judge it, and a person accepts every intent and merges every change.
- The repository is public.

## Open questions

- [ ] Where do the plugin's artefacts live: plain files as the playbook has them (`intent/`, `spec.md`, `plan.md`), a board such as Backlog.md, or something else?
- [ ] Where do the first eval cases come from, before the plugin has a history of its own?
- [ ] How are the plays that need infrastructure (managed settings, deployment, production metrics) exercised and evaluated when there is no production service and possibly no organisation?
- [ ] Which judgements need a model judge at all, and how are human labels collected to calibrate one?
