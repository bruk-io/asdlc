---
kind: intent
author: Bruk Habtu
---
# Intent: an agent captures an intent

## Problem

The goal of this plugin is to match Anthropic's AI-native SDLC workflow. Version 2 has the documents, the lint, the guard and the commands, and a person can drive the loop by hand. What is missing is "the skills per stage and their evals". Without a skill, an agent has nothing telling it how to run a stage, and without evals nobody can tell whether a change to a skill made the agent better or worse.

The first stage is capturing an intent: a person describes a problem, and today nothing turns that into `intent.md` for them.

## Proposed outcome

- A person describes a problem to Claude, and gets an `intent.md` on its own branch as a pull request they can merge or close.
- The intent keeps the person's own wording and facts, and names no solution they did not state.
- Each outcome in it is something a person can judge.
- What nobody knows yet is written as an open question, not guessed.
- The person sees the draft and corrects it before the pull request is opened.
- A request that fits in a handful of tool calls produces no intent.
- The skill arrives with at least two eval cases, one where it should act and one where it should stay out, and the cases can be checked for shape without running a model.

## Affected users and systems

Anyone using the plugin to start a piece of work. The plugin's `skills/` folder, a new `evals/` folder, and the `asdlc` command.

## Constraints

- The agent never merges. Accepting an intent stays a person's decision.
- The skill writes the prose only. Paths, branch names and frontmatter come from `asdlc intent new`.
- The branch changes only `intent.md`, so the guard stays clean.
- Evals never block a pull request.
- The layers hold: decisions in `asdlc/domain`, reading in `asdlc/io`, wording in `asdlc/presentation`.

## Open questions

### Q1: How much of the eval suite arrives with this intent - the case format and a shape check only, or the runner as well?

### Q2: Where do eval cases for a skill live, in one `evals/` folder or beside the skill?

### Q3: Should the skill record when the conversation started, so time to a committed intent can be measured later?
