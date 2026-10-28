---
name: writing-a-contract
description: Write and keep the contract for a large feature that spans repositories - the behaviour and states every client implements, the API between repositories, the analytics events table, the traces and logs, and which child task builds which part - as a document on the board that only the orchestrator changes. Load it when you write the spec for an intent, before splitting it into child tasks, before checking a child's plan against the contract, and when a worker asks for a contract change. Without it, platforms name the same event differently, two tasks build the same endpoint, and plans are approved against a contract nobody wrote down.
---

# Writing a contract

- Owner: the team. Changes arrive as pull requests to `plugins/team/` in the tasks repository.
- Source: this skill and `templates/contract.md` beside it.
- Enforced by: the orchestrator, who checks each child plan against the contract before its engineer approves it, and checks across repositories when the children reach review. Advisory otherwise.

A large feature is built by several workers in several repositories at once, and none of them can see the others' work. The contract is the one place they agree: what the feature does, what crosses each boundary, what is measured and observed, and who builds which piece. If it isn't in the contract, two workers will each decide it differently.

## When to write one

Write a contract when an intent's children touch more than one repository, or more than one layer that another team owns. A feature inside one repository and one layer needs a plan, not a contract.

Write it before the child tasks are split, since the split comes from "Who builds what".

## Writing it

1. Copy `${CLAUDE_PLUGIN_ROOT}/templates/contract.md` to a scratch file and fill it in from the intent and its spec.
2. **Behaviour and states.** Name every state the user or caller can be in, with what they see and the events that move between states. Use the same state names on every platform. Cover offline, empty, error and permission-denied explicitly.
3. **API.** For each operation that crosses a repository, name the owning repository and give the request, response and errors exactly enough that both sides can build against it alone. Say how old clients behave.
4. **Analytics events.** One row per event: its name, every property with its type, the exact trigger, and every platform that sends it. Follow the team's analytics conventions if the team plugin has them; otherwise match the names already in use in the repositories.
5. **Traces and logs.** The spans and log events an on-call engineer needs to follow one request across repositories, with the ids that join them. Follow the team's observability conventions where they exist. No personal data in logs.
6. **Who builds what.** Every part of the contract maps to exactly one child task in one repository, with its dependencies. This table is the split: create the child tasks from it (as drafts, with sizes), then fill in their ids.
7. Put it on the board as a document and link it from the intent and every child:

   ```sh
   asdlc board doc create "Contract: <feature>" -t specification
   asdlc board doc update <doc-id> --content "$(cat <scratch file>)" --tags contract
   asdlc board task edit <intent-id> --add-doc <doc-id>
   asdlc board task edit <child-id> --add-doc <doc-id>
   ```

## Keeping it

- Only the orchestrator edits the contract, with the engineer for anything that changes the spec. A worker who needs a change asks in its task's notes, saying what and why; the orchestrator decides.
- Every change bumps the version, adds a line under "Changes", and puts a note on each affected child task, so its worker re-reads the contract before continuing.
- Before an engineer approves a child's plan, check it against the contract: the states, the API shapes, the event names and properties, the spans. A difference is fixed in the plan or, if the contract was wrong, in the contract first.
- When the children reach review, check across repositories: the same event sent with the same properties everywhere, both sides of each API agreeing.
- Keep the contract, its changes and your checks on the board. A restarted session picks up from the board, and the board is all it will have.
