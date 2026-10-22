---
name: lead
description: Lead a large piece of work - an intent with children across repositories - on the shared board - the spec and contracts as Backlog documents, the breakdown into draft child tasks per repository with sizes and dependencies, asking the person to accept it, deciding contract change requests, checking each child plan against the contract, and checking consistency across repositories at review. Use when you hold or have just claimed the lead on an intent (asdlc lead), when asdlc lead-of says the lead is yours, or when the engineer asks you to take on an intent.
---

# Lead an intent

An intent with children has exactly one lead: the orchestrator holding the atomic claim from `asdlc lead <intent> --as <engineer>.lead`. The lead owns the vision and the breakdown, the contracts between layers and repositories, and their consistency, and escalates to its engineer. Every other orchestrator working on a child reads the lead's documents and reports through the board.

Keep everything on the board. Your claim can go stale and another orchestrator can take over; whatever is only in this conversation is lost to them. Heartbeat the lead while you hold it (`asdlc heartbeat <intent> --as <engineer>.lead`), and give it up with `asdlc release <intent> --as <engineer>.lead` if your engineer stops the work.

You may run your own helper subagents for research or drafting. They follow the same rules.

## 1. The spec

Read the intent: its problem, constraints, open questions and acceptance criteria (`asdlc board task view <intent> --plain`, or `asdlc board draft view <id> --plain` while it is a draft). Settle each open question with the engineer or carry it forward with a reason.

Write the spec as a Backlog document and link it from the intent:

```sh
asdlc board doc create "Spec: <intent title>" -t specification
asdlc board doc update <doc-id> --content "$(cat <<'EOF'
<numbered requirements, the design, areas of concern, and every open question settled or carried forward>
EOF
)"
asdlc board draft edit <intent> --add-doc <doc-id>     # `task edit` once the intent is accepted
```

## 2. The contracts

When children touch more than one repository, or a layer another team owns, write the contract the children build to as a document of its own, linked the same way: what the feature does, what crosses each boundary (APIs, events, schemas), what is measured and observed, and which child builds which part. If the team plugin is installed, its `writing-a-contract` skill and template say how. Only you change a contract.

## 3. The breakdown

Split the intent into draft child tasks, one per piece of work in one repository:

```sh
asdlc board task create "<title>" --draft -p <intent> --project <repo-slug> -l size-<n> \
  --dep <other child>  --ac "<observable result>"  -d "<what and why, citing the spec's requirement numbers>"
```

- `--project` is the repository's slug, `owner-repo` (`asdlc repos` lists the ones registered here). A task's project decides where its worktree is made.
- One size label from the routing table. `size-8` is refused until it is split. `size-1` is for small, mechanical work only: its worker is haiku and follows numbered steps.
- `--dep` for real ordering only: a child that consumes another's API depends on it.
- `-a @<engineer>` reserves a child for that engineer's workers, when the engineer asked for it or only they can do it.
- Drafts under a draft intent are allowed: asdlc records the draft parent itself.

Then ask the person to accept the work: tell your engineer the intent, the spec and contract documents, and the children with their repositories, sizes and dependencies, and ask them to run `asdlc accept <intent>` themselves. It promotes the intent and every draft child in one board commit. You can't run it; the board guard refuses agents.

## 4. Contract change requests

A worker who finds the contract wrong doesn't work around it. It comments on its own task and adds the label:

```sh
asdlc board task edit <task> --add-label contract-change --comment "<what must change and why>"
```

Look for them each round: `asdlc board task list -p <intent> -l contract-change --plain`. Decide each one: change the contract document and say so in a comment on the task, or say no and why. Remove the label once it is answered. A change that affects other children gets a comment on each of them too. Escalate to your engineer when the change alters the spec or what the person accepted.

## 5. Plans against the contract

Before any engineer approves a child's plan, check it against the spec and contracts: the endpoints, events and names it will build match the contract, it builds only its own part, and its proof covers its acceptance criteria. Record the result on the child:

```sh
asdlc board task edit <task> --append-notes "Plan checked against <doc-id> by @<engineer>.lead: <ok, or what must change>"
```

## 6. Consistency at review

When the children reach In Review, read their pull requests together (`--ref` on each task records them): the same names for the same things across repositories, both sides of every boundary agreeing, nothing in the contract left unbuilt. Put what you find on the tasks concerned, and tell your engineer what is ready to merge and in which order.
