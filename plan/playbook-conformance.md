# Plan: the plugin against the playbook, claim by claim

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md)
- Status: draft. Merging this file, after the owner approves it in session, starts the build.
- Delivers: R20 (every change goes through the loop). Later changes in this series deliver R25 (a component whose removal costs nothing becomes an intent to delete it).

We say the plugin implements Anthropic's AI-native SDLC playbook, but the only record of what the playbook asks is the table in `plan/eval-suite.md` and a pasted conversation. "We follow it" rests on one reading. This change writes the playbook down as numbered claims, maps each to what implements and tests it, and fails the build when a claim is unmapped, a mapping points at nothing, or a requirement serves no claim. That last check would have flagged the multi-machine machinery, which no lesson asked for.

It answers one of the two questions the owner raised (did we follow the playbook?). Whether we built the right things is answered by later changes, listed under Not in this change.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `spec/playbook-conformance.md` | yes | One section per play (1 to 12). Each claim has an id (`P3.2`), one sentence in our own words, and a `Where:` line of targets: `skill:<name>`, `agent:<name>`, `hook:<file>`, `script:<file>`, `eval:<case>`, `artefact-check`, or `none: <reason>`. A closing "Beyond the playbook" section lists each requirement that serves no claim, with its reason | R20 |
| `scripts/conformance.py` | yes | The check: every claim has a `Where:` line; every target exists on disk (skill, agent, hook, script, eval case); every `R<n>` in the spec appears in a claim or in "Beyond the playbook"; no claim id is repeated. Takes data, returns findings; the shell only reads files | R20 |
| `tests/test_conformance.py` | yes | One test per finding kind, with a small bad document each, plus one that the real document passes | R20 |
| `scripts/check` | no | Runs the conformance check beside the artefact checks | R20 |
| `plan/playbook-conformance.md` | yes | This plan | R20 |
| `CHANGELOG.md` | no | One line | - |

## What the claims are, and are not

- Written from the lessons the owner pasted, one sentence per thing a lesson says to do or to check, in our own words. The lessons' text is not copied into the repository: the course is Anthropic's, so the file carries claims and a lesson reference only.
- A claim with `none: <reason>` is allowed and is the honest answer for plays 11 and 12 today. The check requires the reason, so a gap is written down instead of left out.
- The mapping says where a claim is implemented or tested, not that it passes. Whether the evals pass is the gate's job.

## Order of work

1. Read the pasted lessons again and write the claims, play by play, with their `Where:` lines. Plays 1 to 3 first, then the rest, committing after each group.
2. Write `scripts/conformance.py` and its tests against two small documents (one good, one with each fault).
3. Run it on the real document, fix what it finds (a real gap goes in as `none:` with its reason; a wrong target is corrected), and list every requirement that serves no claim under "Beyond the playbook".
4. Wire it into `./scripts/check`. Run the check and paste its result.

## Risks

- **I mis-state a lesson.** Medium. The claims are my reading. Mitigation: the owner reads the file in the pull request, and a later change gives the playbook and the repo (not this plan) to a fresh agent to find gaps.
- **A mapping that exists but proves nothing.** Medium. `eval:small-request-no-intent` says a case covers a claim, not that it covers it well. The check only guarantees the target exists; the with/without-plugin comparison in a later change is what tests value.
- **The document goes stale.** Low. A new skill, hook or requirement that serves no claim fails the check until it is placed or listed as beyond the playbook.
- **Over-mapping to look compliant.** Medium. Each `Where:` names one target per claim where it can, and "Beyond the playbook" is a first-class section, not an apology.

## Not in this change

Each is its own intent and plan, in this order:

1. The history audit: a script over merged pull requests checking each had a plan, approved before the code, and a review.
2. The with-and-without-plugin comparison: the full suite at 3 trials in both arms, reading where the plain agent does as well.
3. An independent read: a fresh agent given the playbook and the repository only, asked for gaps.
4. A new-user trial on an empty repository, with thresholds set before looking (time to a committed intent, first-pass CI, share of review findings that are real).
5. Component ablation (R25).

## Proof

- `./scripts/check` passes, its output pasted in the pull request.
- The new check fails on a document with an unmapped claim, a missing target, a repeated id and an unplaced requirement (the tests), and passes on the real one.
- The pull request lists every claim mapped to `none:` and every requirement under "Beyond the playbook", so the owner sees the gaps at a glance.
