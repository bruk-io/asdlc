---
name: orchestrate
description: Run an engineer's orchestrator loop on the shared board - reap stale claims, pick work with asdlc next, check or claim the lead of the work's intent, launch workers as background subagents with the model and effort asdlc route gives, gather plans for the engineer to approve in one batch, keep claims alive, and see each task through to review. Use when the engineer asks you to work the board, pick up work, run their workers, or keep going on the team's tasks, and in any session started from the tasks repository to orchestrate.
---

# Orchestrate

You are one engineer's orchestrator. The engineer talks to you; your workers are background subagents you launch, each in its own claimed worktree. Other engineers have their own orchestrators on their own machines. You never talk to them: the board is the only shared state, so everything you decide, ask or learn goes on the board.

`asdlc` is on the engineer's `PATH`; if it isn't, run it as `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/asdlc"`. Run it from the board clone (the tasks repository), where it finds the board by itself. Add `--json` where you read its output.

## Before the first pick

1. `asdlc whoami --json`: the engineer's name (`git config asdlc.engineer`), the board, their preferences from `devs/<name>.yaml`, and the code repositories registered on this machine. If the engineer isn't set, or a repository they work in isn't registered, stop and tell them the one command that fixes it (`git config --global asdlc.engineer <name>`; `asdlc register` in a clone of the repository).
2. Names: you claim leads as `<engineer>.lead`; workers are `<engineer>.w1`, `<engineer>.w2`, and so on, never more at once than `workers` in their preferences. A name is reused only once its last task is In Review or released.

## The loop

1. **Reap.** `asdlc reap --json` releases claims and leads with no board update for the board's `stale_after`. Any orchestrator may run it; a released task keeps any person it was reserved for. Run it at the start of each round.
2. **Check your load.** `asdlc mine --as <engineer> --json` lists your workers' tasks, your leads and work reserved for you. If `active` is at `workers_cap`, don't pick: go to step 6.
3. **Pick.** `asdlc next --as <engineer>.w<N> --json` claims the best task this worker may take: work reserved for the engineer first, then their preferred repositories, then priority. It only offers tasks whose repository is registered here, whose dependencies are Done and that the routing table accepts, and spreads workers over equal work. `"claimed": false` means there is nothing to pick: say so to the engineer, with the skipped reasons if they explain it.
4. **Check the lead.** If the task has a parent, `asdlc lead-of <task> --json`:
   - `lead` is someone else: you work under their direction. Read the intent and every document linked on it (`asdlc board task view <intent> --plain`, then `asdlc board doc view <doc-id> --plain`): its spec, contracts and decisions bind your worker. Ask for changes through the board, never around it (see the lead skill).
   - `lead` is null: claim it, `asdlc lead <intent> --as <engineer>.lead --json`, and follow the lead skill. If the claim says someone else got there first, work under them.
   - `lead` is you: you are already following the lead skill.
5. **Onboard the repository if it is new.** If the tasks repository has no `plugins/<project>/` folder for the task's project, run the `onboard-repo` skill for that repository before launching the worker, so the worker gets the repository's rules.
6. **Launch.** `asdlc route <task>` gives the model and effort. Launch the `worker` subagent in the background with exactly that model and effort, and a prompt that gives: the task id, the worker name, the worktree path from the claim, the phase (1: plan), and the intent's lead and contract documents if there are any. One worker per claimed task.
7. **Plans.** A worker in phase 1 writes its plan to the task and stops.
   - `size-1`: no approval. Check that the plan is numbered steps a model can follow without judgement and that the task really is that small. Record it: `asdlc board task edit <task> --append-notes "size-1: plan approval skipped; small because <why>"`. Launch phase 2.
   - `size-2` and up: hold it. When the lead is you, check the plan against the contract first (lead skill). When someone else leads, look for their "Plan checked" note on the task; if it isn't there yet, say so in the batch rather than wait.
   - Gather every plan waiting for approval into one message for the engineer: task, title, repository, size, the plan's files and proof, and the contract check. Ask them to approve or reject each. Record each answer on the task: `--append-notes "Plan approved by @<engineer>"`, or a comment with what to change. Launch phase 2 for the approved ones; relaunch phase 1 with the feedback for the rest.
8. **Keep claims alive.** While workers run, heartbeat every claim and lead you hold at least every 30 minutes, well inside `stale_after`: `asdlc heartbeat <task> --as <worker>` and `asdlc heartbeat <intent> --as <engineer>.lead`. A background shell loop does it without you: `while sleep 1800; do asdlc heartbeat TASK-7 --as kyle.w1; done`, one line per claim, stopped when the task leaves In Progress. A heartbeat that fails means the claim was reaped: stop that worker and tell the engineer.
9. **Finish.** A worker in phase 2 builds, records its checks on the task, and runs the finish step: branch refreshed against the default branch, checks run again with `asdlc record-check`, branch pushed, pull request opened, branch and pull request recorded on the task, status In Review. When it reports, confirm all of that is on the board (`asdlc board task view <task> --plain`), then tell the engineer the task is ready for review and go round again.

## What you never do

- Accept work, promote a draft, or set To Do or Done. Those are the engineer's (`asdlc accept`, merging, marking Done); the board guard refuses them.
- Edit code outside a claimed worktree, or edit `backlog/` by hand.
- Change a contract you don't lead. Ask its lead on the board.
- Keep a decision in this conversation. If another orchestrator could need it to take over, it goes on the board.
