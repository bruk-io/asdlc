---
name: plan-change
description: Write the plan for one change before any file is edited - the files that change, the order of work, the risks and the proof, citing the spec's requirements - and open it as a pull request whose merge approves it. Use after a spec is approved, before implementing a change, when entering plan mode, or when asked how a change will be built.
---

# Plan a change

A plan moves design review ahead of the code. Reviewing a plan costs minutes; reviewing the same mistake in a finished diff costs a rewrite. The plan is also what the change is checked against later, so it has to say concretely where the work will land.

## Read before writing

Read the approved spec and its intent, and the parts of the codebase the change touches. Plan mode is a good way to do this, since nothing can be edited until the plan is approved. If there is no approved spec, the change is either small enough to do directly or it needs an intent first.

## Write it

Copy `${CLAUDE_PLUGIN_ROOT}/templates/plan.md` to `plan/<short-slug>.md` and fill it in.

- **Delivers** cites the spec's requirement numbers this change meets.
- **Files that change** names every file, in backticks, with what changes in it. Later checks compare this list with the files the commits actually touch.
- **Order of work** is numbered, each step small enough to check before the next starts. Start with whatever gives the work a feedback loop.
- **Risks** are the real ones: what could break, how likely, and what is done about it.
- **Proof** is checks that show the change works, as commands or observable results, not a description of effort.

## Challenge it

Before asking for approval, ask what could break, which step carries the most risk, and which alternatives were rejected and why. Refine the plan until someone who never saw the conversation could build the change from the file alone.

## Check it and open the gate

Run `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/artefacts.py" .` and fix what it reports. Commit the plan alone on `plan/<short-slug>`, push it, and open a pull request; merging approves it. Name any decision the approver is making by merging.

## When the work drifts

If implementation has to depart from the plan, update the plan in the same commit as the change and say why in the commit message. A large departure is a reason to stop and propose a new plan rather than push through.
