---
name: plan-change
description: Write the plan for one claimed task before any file is edited - the files that change, the order of work, the risks and the proof, as numbered steps for a size-1 task - into the task's plan section on the shared board, for the engineer to approve. Use when a worker is in its planning phase, before implementing a task, when entering plan mode, or when asked how a change will be built.
---

# Plan a change

A plan moves design review ahead of the code. Reviewing a plan costs minutes; reviewing the same mistake in a finished diff costs a rewrite. The plan is also what the change is checked against later, so it has to say concretely where the work will land.

## Read before writing

Read the task (`asdlc board task view <task> --plain`): its description, acceptance criteria, notes and comments. If it has a parent intent, read the intent and every document linked on it, its spec and contracts above all: the plan must build this task's part of the contract and nothing else. Then read the parts of the codebase the change touches, in the task's worktree. Plan mode is a good way to read, since nothing can be edited there.

## Write it

The plan goes in the task's plan section:

```sh
asdlc board task edit <task> --plan "$(cat <<'EOF'
## Files that change
- `<path>`: <what changes in it>

## Order of work
1. <A step small enough to check before the next one starts.>

## Risks
- <What could break, how likely, and what is done about it.>

## Proof
- <A check that shows the change works, as a command or an observable result.>
EOF
)"
```

- **Files that change** names every file, in backticks, with what changes in it. Make it the real list: the review compares it with the files the commits touch.
- **Order of work** is numbered, each step small enough to check before the next starts. Start with whatever gives the work a feedback loop.
- **Risks** are the real ones.
- **Proof** is the repository's checks and the acceptance criteria they demonstrate, as commands. The worker records them with `asdlc record-check`.

### A size-1 task

A `size-1` task is built by a small model that follows steps, not intent, and its plan is not approved by a person. Write its order of work as numbered steps, each one exact: the file, the change, the command to run. If you can't write it that way, the task isn't size-1: say so in the task's notes, so the orchestrator can resize it.

## Challenge it

Before handing it over, ask what could break, which step carries the most risk, and which alternatives were rejected and why. Check it against the contract: names, endpoints and events as the contract has them. Refine it until someone who never saw this conversation could build the change from the task alone.

Then stop. For a task of size 2 or more, the engineer approves the plan in their orchestrator's batch, and the approval is recorded in the task's notes before building starts.

## When the work drifts

If building has to depart from the plan, update the plan on the task (`--plan`, or `--append-plan`) and say why in the notes. A large departure is a reason to stop and ask for a new approval rather than push through.

## In a repository that keeps plans as files

This plugin's own repository records its plans as files under `plan/`, approved by merging a pull request, as its CLAUDE.md says. There, copy `${CLAUDE_PLUGIN_ROOT}/templates/plan.md` to `plan/<short-slug>.md`, cite the spec's requirement numbers in **Delivers**, check it with `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/artefacts.py" . plan/<short-slug>.md`, and open it as a pull request on `plan/<short-slug>`.
