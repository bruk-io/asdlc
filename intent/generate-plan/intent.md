---
kind: intent
author: Bruk Habtu
---
# Intent: a skill that generates a plan

## Problem

The plugin can capture an intent and write its spec, but once a spec is merged the plan is still written by hand from the template. Nothing tells Claude how to run that stage, and nothing measures whether it does it well.

## Proposed outcome

- When a spec is on `main`, a person asks Claude for its plan and gets `plan.md` on its own branch, as a pull request they can merge or close.
- The plan does what Anthropic's AI-native SDLC course asks of a plan:
  - it lists the files that change, and every file it lists as existing is in the repository
  - its order of work is steps, and a step that delivers a requirement says which
  - every requirement in the spec is delivered by some step
  - its risks include each area of concern the spec raised that the work can run into
  - its proof says how each requirement will be shown to be met
- Someone who never saw the conversation could build from it.
- Lint is clean on the plan it writes.
- The skill arrives with eval cases, at least one where it must act and one where it must stay out.

This is only the plan stage, from a merged spec to an open pull request. Sizing, cutting tasks and building are later intents.

## Affected users and systems

Anyone using the plugin after a spec is merged. The plugin's `skills/` and `evals/` folders, and the `asdlc` command.

## Constraints

- Claude never merges. Accepting a plan stays a person's decision.
- The skill writes the prose only. The path, the branch name and the frontmatter come from `asdlc plan new`.
- The branch changes only `plan.md`, so the guard stays clean.
- A plan is not started before its spec is on `main`.
- The layers in the package hold.

## Open questions

### Q1: The course makes its plan in Claude Code's plan mode and commits the approved plan as `plan.md`. Should this skill work in plan mode, or in an ordinary session?

### Q2: What does a plan do with a step that depends on a question the spec carried and nobody has answered?

### Q3: A small intent is built on `change/<slug>` with its plan as the first commit. Should the skill write that plan too, or only the one on `plan/<slug>`?
