---
kind: intent
author: Bruk Habtu
---
# Intent: Specs say which policies they applied

## Problem

Specs in this repository apply no policy.

Anthropic's AI-native SDLC course has an organisation write its policies as skills. Its lesson on the spec lists as a prerequisite "brand, security, compliance, and UX policies written as skills". Its prompt says "Apply the skills available to you so the plan conforms to our brand guidelines, security policies and UX standards." and "Describe clearly any areas of concern, especially where you cannot satisfy contradicting policies." Its example spec has the line "Skills applied: secure-api-review, brand-voice, portal-ux." Its lesson on skills says "When the policy changes, change the skill and have the policy owner sign off on the change." and "A policy that must always hold needs something deterministic behind the skill, such as a hook that blocks the action".

Here, a spec's frontmatter can carry `policies:`, and lint lets it through, but nothing writes it and nothing checks it. The generating-a-spec skill says nothing about policy skills. The only policy named anywhere is `pii-in-logs` in the worked example, which is an example name and not a skill that exists. The spec for the spec skill carried this as an open concern, its C1.

This repository does have a policy of its own now: the authoring plugin, which is the requester's standard for writing skills and hooks. It was applied by hand while the four skills were written, and nothing records that. On 2026-11-17 its auditor was run over the plugin after the fact, and it reported 14 findings. One was a conflict between the policy and an intent: the policy says a step a script can decide belongs in code, and the generate-tasks intent said the command must not change. That came out after the skill was built. That kind of conflict should be in front of the requester when the spec is written.

## Proposed outcome

- When a spec is written in a repository that has policy skills, the spec says which ones it applied.
- Where a policy and the intent cannot both be met, or two policies cannot, the spec has an area of concern that says so and names who owns the policy, before anything is built.
- A policy name in a spec that is not a skill here is caught by lint.
- This repository says the authoring plugin is its policy, so a session here has it.

## Affected users and systems

- Whoever asks for a spec and accepts it.
- Whoever owns a policy, because the concerns come to them.
- Whoever plans and builds from the spec.
- The generating-a-spec skill, the spec format and its lint, and `asdlc spec new`.

## Constraints

- The four specs on `main`, which name no policy, stay valid.
- A repository with no policy skills gets its specs as it does today.
- `asdlc spec new` keeps working for someone who passes nothing new.
- The spec skill's three eval cases still pass.
- Accepted documents are not edited: the generate-spec intent and its spec stay as they are.
- This work's spec says what it replaces.
- Running a policy skill against a finished spec as a check of its own is not part of this.
- A reviewer that checks a pull request against the policies is not part of this.

## Open questions

### Q1: How does a policy's name get into the frontmatter, since the command writes it and the skill may not type it?

### Q2: How does the spec skill tell a policy skill from any other skill a session happens to have?

### Q3: Where is a policy's owner written down?

### Q4: Does a skill that comes from a plugin count the same as one in the repository's own `.claude/skills/`, and how would lint find it to check a name?

### Q5: The authoring plugin is not in this repository and is not public. How does a public repository say a policy is its own when others cannot install it?
