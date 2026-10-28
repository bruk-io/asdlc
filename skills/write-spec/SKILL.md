---
name: write-spec
description: Write the spec for an intent on the board as a Backlog document - numbered requirements, the design, areas of concern, and every open question from the intent settled or carried forward with a reason - and link it from the intent. Use when an intent has no spec yet, when asked to write or revise a spec, and before breaking an intent into child tasks.
---

# Write a spec

The spec is the second artefact of the loop: what will be built, as requirements the children and their plans can cite by number. It answers the intent; it doesn't redo it. Keep it on the board as a document so another orchestrator can take over from it (`templates/spec.md` shows the shape).

Read the intent: its problem, constraints, open questions and acceptance criteria (`asdlc board task view <intent> --plain`, or `asdlc board draft view <id> --plain` while it is a draft). Settle each open question with the engineer, or carry it forward with a reason. Apply the repository's policy skills while you write.

```sh
asdlc board doc create "Spec: <intent title>" -t specification
asdlc board doc update <doc-id> --content "$(cat <<'EOF2'
<numbered requirements, the design, areas of concern, and every open question settled or carried forward>
EOF2
)"
asdlc board draft edit <intent> --add-doc <doc-id>     # `task edit` once the intent is accepted
```

- One checkable requirement per number: someone can say yes or no to it from the result.
- Where policies conflict or a requirement can't be met cleanly, put it under areas of concern for the engineer to decide. Don't resolve it silently.
- Say what the spec leaves out.

When children touch more than one repository, or a layer another team owns, the contract is a document of its own (the orchestrate skill says how a change to it is decided). Next: the breakdown (break-down-intent skill).
