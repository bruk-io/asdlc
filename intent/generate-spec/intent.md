---
kind: intent
author: Bruk Habtu
---
# Intent: a skill that generates a spec

## Problem

The plugin can capture an intent now, but once an intent is merged the spec is still written by hand from the template. Nothing tells Claude how to run that stage, and nothing measures whether it does it well.

## Proposed outcome

- When an intent is on `main`, a person asks Claude for its spec and gets `spec.md` on its own branch, as a pull request they can merge or close.
- The spec does what Anthropic's AI-native SDLC course asks of a spec:
  - its requirements are numbered, and each can be checked
  - its design fits the code that is already there
  - it says how each constraint in the intent is met
  - every open question from the intent is answered or carried forward
  - its areas of concern each have an owner, especially where two things cannot both be satisfied
- If the new spec ends a requirement that is in force, it says which one it replaces.
- Lint is clean on the spec it writes.
- The skill arrives with eval cases, at least one where it must act and one where it must stay out.

This is only the spec stage, from a merged intent to an open pull request. Planning and tasks are later intents.

## Affected users and systems

Anyone using the plugin after an intent is merged. The plugin's `skills/` and `evals/` folders, and the `asdlc` command.

## Constraints

- Claude never merges. Accepting a spec stays a person's decision.
- The skill writes the prose only. The path, the branch name and the frontmatter come from `asdlc spec new`.
- The branch changes only `spec.md`, so the guard stays clean.
- A spec is not started before its intent is on `main`.
- The layers in the package hold.

## Open questions

### Q1: Should a spec name the policy skills it applied, the way the course's example has a "Skills applied" line, when this plugin ships no policy skills?

### Q2: How can an eval case show that a design fits the existing code without leaning on a judge?
