---
name: capture-intent
description: Write new work down as an intent on the shared board - a draft of type intent with the problem, constraints and open questions in the requester's own words, and the outcomes they want as acceptance criteria - for a person to accept. Use when someone describes a problem or a piece of work bigger than one small change, asks to write an intent or put work on the board, or when an alert or incident needs to become work. Not for questions, bug reports with an obvious fix, or work that fits in a handful of tool calls.
---

# Capture intent

An intent is the first artefact of the loop: what the person with the problem wants, in their words, before anyone decides how. Everything after it (the spec, the breakdown, the plans, the review) is judged against it, so it is worth getting right while changing it costs a sentence.

Small work doesn't need one. If the request fits in a handful of tool calls, do it directly.

## Interview first

When someone describes a problem rather than a finished intent, ask what an analyst would ask until the answers are concrete: what they can't do today, who is affected, what better looks like, what must not break, and what is out of scope. Keep their words. Translating the problem into engineering terms is the spec's job, and doing it here loses what they meant.

If they are not there to ask, write the draft from what you have and turn every gap into an open question.

An intent that comes from an alert or an incident is written the same way: the anomaly and its evidence are the problem, and whatever the evidence can't settle is an open question.

## Write it on the board

The intent is a draft of type `intent`. Its description has three sections, and each outcome the requester wants is an acceptance criterion:

```sh
asdlc board task create "<what the requester wants, in their words>" --draft --type intent \
  --ac "<an outcome, phrased so a check or a reviewer can judge it>" \
  --ac "<another outcome>" \
  -d "$(cat <<'EOF'
Requested by @<name>.

## Problem

<What can't be done today, and why it matters, in the requester's own terms. Not a solution.>

## Constraints

<What must hold or must not break while the work is done: the work's constraints, not how this session runs.>

## Open questions

- [ ] <What nobody knows yet, one question per line, in a stable order. If there are none: None.>
EOF
)"
```

- Leave solutions out unless the requester stated one as a constraint.
- The intent names no repository (`--project`) and has no size: its lead splits it into child tasks that do.
- Don't assign it. An assignee on accepted work reserves it for that person's workers.
- `asdlc` prints the draft's id, `DRAFT-<n>`. Draft ids are reused once a draft is promoted, so refer to it by title as well as id.

## Open the gate

If the person is there, show them the draft (`asdlc board draft view <id> --plain`) and correct it with them; it is their problem, in their words. Point out anything you guessed.

Stop there. The intent's lead (the lead skill) writes the spec and drafts the child tasks under it, and then the person accepts the whole of it with `asdlc accept <id>`, in their own terminal. Agents can't accept work; the board guard refuses it.

## In a repository that keeps intents as files

This plugin's own repository records its intents as files under `intent/` and accepts them by merging a pull request, as its CLAUDE.md says. There, copy `${CLAUDE_PLUGIN_ROOT}/templates/intent.md` to `intent/<short-slug>.md`, fill it in, check it with `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/artefacts.py" . intent/<short-slug>.md`, and open it as a pull request on `intent/<short-slug>` whose merge accepts it.
