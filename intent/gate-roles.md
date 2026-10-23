# Intent: the right person at each gate

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-10-23

## Problem

The playbook names a different person at each gate: the product owner accepts an intent and approves its spec, policy owners settle the concerns a spec flags, the engineer approves a routine plan, a tech lead approves a high-risk plan or spec, a code owner merges, and on-call triages what monitoring finds. In asdlc every gate is "the engineer", whoever ran the orchestrator.

On top of that, `asdlc accept` takes the intent, its spec and its whole breakdown in one step. So the lead spends a strong-model session writing a spec and splitting the work before anyone has agreed the problem is worth solving, and the survival rate measures the bundle rather than the intent. On my team a PM owns the problem and a tech lead owns the risky calls; asdlc gives them no gate of their own.

## Proposed outcome

- Each gate on a board names who may pass it, set per board, and asdlc refuses the gate to anyone else, saying who can pass it.
- An intent can be accepted on its own, before its lead writes the spec, with the spec and breakdown accepted after. A board can keep accepting everything in one step.
- Work marked high-risk sends its plan approval, and its spec's, to a tech lead.
- A spec's areas of concern each name the policy owner who settles it, and the breakdown can't be accepted while one is open.
- `asdlc stats` reports each gate's wait by who passed it.

## Affected users and systems

- Engineers, product managers, tech leads and policy owners on the team.
- `asdlc accept` and `asdlc approve`, the board guard, the lead and capture-intent skills, `devs/<name>.yaml` and `asdlc.toml`, and `asdlc stats`.

## Constraints

- Agents still pass no gate.
- A small team where one person holds every role gets no extra steps.
- Git records who passed each gate and when (R2).
- Work already accepted on a board keeps working.

## Open questions

- [ ] Where are roles set: each person's `devs/<name>.yaml`, the board's `asdlc.toml`, or both?
- [ ] What marks work high-risk, and who sets it: the lead, the engineer, or a rule over the files a plan touches?
- [ ] Is accepting the intent first the default, or something a board turns on?
- [ ] How does a product manager without the command line or a tasks clone pass their gate, or capture an intent in the first place?
- [ ] Is the merge gate's person (a code owner) asdlc's to check, or left to the forge's branch protection?
