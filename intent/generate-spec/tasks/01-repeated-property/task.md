---
kind: task
step: 1
delivers: [R17, R18]
size: 1
---
# Task: lint finds a property written twice, and a concern with no owner

## What to build

Step 1 of the plan. Under a heading, a second `- key: value` line with the same key silently replaces the first. A requirement with two `- replaces:` lines therefore ends only the last one, and lint is clean.

- An `Item` in `src/asdlc/domain/documents.py` also carries the keys that were written more than once.
- `parse` reports each under the `property` rule. The message names the heading and the key, and says a requirement that ends two requirements is written as two.
- `parse` also reports a `### C<n>:` heading with no `- owner:` on the line under it, under a new `owner` rule.

## Done when

- A requirement with two `- replaces:` lines is one `property` finding that names the heading and `replaces`.
- A requirement with one `- replaces:` line, and a step with one `- delivers:` line, are not findings.
- A concern with no owner, and one whose owner is written under its text, are each an `owner` finding. A concern with its owner under the heading is not.
- The example under `examples/claims` still lints clean.
- `just check` passes.
