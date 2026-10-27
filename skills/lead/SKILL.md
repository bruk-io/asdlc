---
name: lead
description: Hold the lead of a large piece of work - an intent with children across repositories - on the shared board: the claim, the contracts between repositories, deciding contract change requests, checking each child plan against the contract, and checking consistency across repositories at review. Sequences the write-spec and break-down-intent skills. Use when you hold or have just claimed the lead on an intent (asdlc lead), when asdlc lead-of says the lead is yours, or when the engineer asks you to take on an intent.
---

# Lead an intent

An intent with children has exactly one lead: the orchestrator holding the atomic claim from `asdlc lead <intent> --as <engineer>.lead`. The lead owns the vision and the breakdown, the contracts between layers and repositories, and their consistency, and escalates to its engineer. Every other orchestrator working on a child reads the lead's documents and reports through the board.

Keep everything on the board. Your claim can go stale and another orchestrator can take over; whatever is only in this conversation is lost to them. The orchestrator heartbeats the lead at the top of each round (`asdlc heartbeat <intent> --as <engineer>.lead`, orchestrate step 2), reading the intent's id from `asdlc mine --as <engineer> --json` each time rather than remembering it: when the person accepts the intent its id changes from `DRAFT-<n>` to `TASK-<n>`, and Backlog gives the old draft id to the next new draft. Give the lead up with `asdlc release <intent> --as <engineer>.lead` if your engineer stops the work.

Run every command from the tasks clone, where your session started; `asdlc` finds the board from there. To read a code repository, use git with `-C` and its path, such as `git -C <repo> ls-files`, and the Read tool on absolute paths (`asdlc repos` gives the paths), never a `cd` first: Claude Code asks a person before any line that changes directory and runs git.

You may run your own helper subagents for research or drafting. They follow the same rules.

## 1. The spec

Write it with the write-spec skill and link it from the intent.

## 2. The contracts

When children touch more than one repository, or a layer another team owns, write the contract the children build to as a document of its own, linked the same way: what the feature does, what crosses each boundary (APIs, events, schemas), what is measured and observed, and which child builds which part. If the team plugin is installed, its `writing-a-contract` skill and template say how. Only you change a contract.

## 3. The breakdown

Draft the children and ask the person to accept the work with the break-down-intent skill.

## 4. Contract change requests

A worker who finds the contract wrong doesn't work around it. It comments on its own task and adds the label:

```sh
asdlc board task edit <task> --add-label contract-change --comment "<what must change and why>"
```

Look for them each round: `asdlc board task list -l contract-change --plain` lists every task asking, at any depth, and `asdlc lead-of <task> --json` says which intent each one is under; answer those under yours. Decide each one: change the contract document and say so in a comment on the task, or say no and why. Remove the label once it is answered. A change that affects other children gets a comment on each of them too. Escalate to your engineer when the change alters the spec or what the person accepted.

## 5. Plans against the contract

Before any engineer approves a child's plan (with `asdlc approve`, in their own terminal), check it against the spec and contracts: the endpoints, events and names it will build match the contract, it builds only its own part, and its proof covers its acceptance criteria. Record the result on the child:

```sh
asdlc board task edit <task> --append-notes "Plan checked against <doc-id> by @<engineer>.lead: <ok, or what must change>"
```

## 6. Consistency at review

When the children reach In Review, read their pull requests together (`--ref` on each task records them): the same names for the same things across repositories, both sides of every boundary agreeing, nothing in the contract left unbuilt. Put what you find on the tasks concerned, and tell your engineer what is ready to merge and in which order.
