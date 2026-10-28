---
name: break-down-intent
description: Split an intent and its spec into draft child tasks on the board, one per piece of work in one repository, with sizes, dependencies and acceptance criteria, then ask the person to accept the whole of it. Use when an intent's spec is written and it has no children, when asked to break work down or split a task, and when a size-8 task has to be split.
---

# Break down an intent

The breakdown turns the spec into work a single worker can plan and finish. Each child cites the spec's requirement numbers, so review can trace every requirement to a task and every task to a requirement.

```sh
asdlc board task create "<title>" --draft -p <intent> --project <repo-slug> -l size-<n> \
  --dep <other child>  --ac "<observable result>"  -d "<what and why, citing the spec's requirement numbers>"
```

- `--project` is the repository's slug, `owner-repo` (`asdlc repos` lists the ones registered here). A task's project decides where its worktree is made.
- One size label from the routing table. `size-8` is refused until it is split. `size-1` is for small, mechanical work only: its worker is haiku and follows numbered steps.
- `--dep` for real ordering only: a child that consumes another's API depends on it.
- `-a @<engineer>` reserves a child for that engineer's workers, when the engineer asked for it or only they can do it.
- Drafts under a draft intent are allowed: asdlc records the draft parent itself.

Then ask the person to accept the work: tell your engineer the intent, the spec and contract documents, and the children with their repositories, sizes and dependencies, and ask them to run `asdlc accept <intent>` themselves. It promotes the intent and every draft under it, at any depth, in one board commit, and comments the new ids on the intent (`DRAFT-1 -> TASK-4`, and so on); each promoted task keeps its old draft id as `asdlc_accepted_from`. You can't run it; the board guard refuses agents. From then on use the new ids: `asdlc mine` lists your lead under its new id with the draft id it had.
