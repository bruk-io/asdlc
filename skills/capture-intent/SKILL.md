---
name: capture-intent
description: Write new work down as an intent - the problem, the outcome wanted, who it affects, its constraints and open questions, in the requester's own words - and open it as a pull request whose merge accepts it. Use when someone describes a problem or a piece of work bigger than one small change, asks to write an intent, or when an alert or incident needs to become work. Not for questions, bug reports with an obvious fix, or work that fits in a handful of tool calls.
---

# Capture intent

An intent is the first artefact of the loop: what the person with the problem wants, in their words, before anyone decides how. Everything after it (the spec, the plan, the review) is judged against it, so it is worth getting right while changing it costs a sentence.

Small work doesn't need one. If the request fits in a handful of tool calls, do it directly.

## Interview first

When someone describes a problem rather than a finished intent, ask what an analyst would ask until the answers are concrete: what they can't do today, who is affected, what better looks like, what must not break, and what is out of scope. Keep their words. Translating the problem into engineering terms is the spec's job, and doing it here loses what they meant.

If they are not there to ask, write the draft from what you have and turn every gap into an open question.

## Write it

Copy `${CLAUDE_PLUGIN_ROOT}/templates/intent.md` to `intent/<short-slug>.md` in the repository and fill it in.

- Proposed outcomes are phrased so a check or a reviewer can judge them later.
- Every open question is one unticked checkbox line, with nothing else in the section. The spec answers each one or carries it forward by number ("intent question 2"), so keep them separate and in a stable order. If there are none, the section says `None.`
- Leave solutions out unless the requester stated one as a constraint.

An intent that comes from an alert or an incident is written the same way: the anomaly and its evidence are the problem, and whatever the evidence can't settle is an open question.

## Check it and open the gate

Run `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/artefacts.py" . intent/<short-slug>.md` from the repository root and fix what it reports. It reports on that file only; leave the rest of the repository alone.

If the person is there, show them the draft and let them correct it before it is committed; it is their problem, in their words. Then commit the intent alone on a branch named `intent/<short-slug>`, push it, and open a pull request against `main`. Say in its description that merging accepts the intent and closing rejects it, and point out anything you guessed.

Stop there. The person with the problem decides by merging; the spec starts after that.
