---
kind: plan
---
# Plan: a skill that generates a spec

## Files that change

- src/asdlc/domain/documents.py
- tests/domain/test_documents.py
- plugins/asdlc/skills/generating-a-spec/SKILL.md (new)
- plugins/asdlc/evals/spec-from-an-accepted-intent/case.yaml (new)
- plugins/asdlc/evals/spec-from-an-accepted-intent/scaffold.sh (new)
- plugins/asdlc/evals/spec-with-a-conflict/case.yaml (new)
- plugins/asdlc/evals/spec-with-a-conflict/scaffold.sh (new)
- plugins/asdlc/evals/spec-waits-for-the-merge/case.yaml (new)
- plugins/asdlc/evals/spec-waits-for-the-merge/scaffold.sh (new)
- tests/test_evals.py
- README.md
- CLAUDE.md

## Order of work

This is built on top of capture-intent's four tasks. It needs their session install, their shape check and `just eval`.

### Step 1: Lint finds a property written twice under one heading
- delivers: R17

`items` in `src/asdlc/domain/documents.py` reads the `- key: value` lines under a heading into a mapping, so a second line with the same key replaces the first. An `Item` will also carry the keys that were repeated, and `parse` will report each under the `property` rule. The message says a heading takes a property once, and that a requirement ending two requirements is written as two.

It comes first because the skill's cases lean on it: a spec with two `- replaces:` lines has to fail lint, or the case that checks `- replaces:` can pass on a spec that leaves a requirement in force.

### Step 2: The skill and its three cases
- delivers: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16

One step, because `just check` fails on a skill that lands without both kinds of case.

**The skill.** `plugins/asdlc/skills/generating-a-spec/SKILL.md`. Its description says when it loads: someone asks for the spec, the requirements or the design of an intent (R1). Its body is the seven steps of the spec's design, in that order (R2 to R15). Three rules need spelling out. The first two are there because a run is one turn and cannot ask:

- An answer comes from the intent, the code or the requester. Anything else is carried (R8).
- A requirement ends one requirement. To end two, the spec has a requirement for each (R11).
- A concern's owner is a person or team the intent or the requester named. When none fits, it is the intent's author, and the draft says so (R10).

**The cases.** Each `scaffold.sh` builds its repository with plain git and files written in the script. `asdlc` is not there when a scaffold script runs, so the documents are written out in full. Each prompt asks for the spec of one named intent and says nothing else.

- `spec-from-an-accepted-intent`, tagged `generating-a-spec` and `acts`. `main` holds an accepted intent, `claim-steps`, with two constraints and two questions, and a small module, `claims_gateway.py`, that the intent never mentions. That module answers the first question. Nothing answers the second. Graders open `intent/claim-steps/spec.md` by path:
  - `asdlc spec new` ran, and `spec.md` is the only file created (R2, R14);
  - each constraint's words are in a table row (R6);
  - `### Q1:` is followed by `- answer: answered`, and `### Q2:` by `- answer: carried` (R7, R8);
  - no `### C<n>:` lacks an `- owner:` (R10);
  - `claims_gateway` appears in the spec (R5);
  - no placeholder from the template is left, and nothing was pushed (R12, R15).

  A judge checks that each requirement can be answered yes or no (R4).
- `spec-with-a-conflict`, tagged `generating-a-spec` and `acts`. `main` also holds an earlier intent whose spec has a requirement in force, and the new intent ends it. The new intent has two constraints that cannot both hold. Patterns check for `- replaces:` naming the earlier requirement (R11) and for a concern that names both constraints and has an owner (R9, R10). A judge checks that the requirements do not satisfy one constraint and drop the other without saying so (R9).
- `spec-waits-for-the-merge`, tagged `generating-a-spec` and `stays-out`. The intent is on the branch `intent/claim-steps` and not on `main`. Patterns check that no `spec.md` was created, that no command made a `spec/` branch by hand, and that the answer says the intent has to be merged first (R3).

**A check on the scaffolds.** `tests/test_evals.py` gains a test that runs every case's `scaffold.sh` in a temporary folder and runs `asdlc document check` on what it built. A scaffold whose documents no longer fit the format then fails `just check`, not a paid run.

`README.md` gains the skill in its table. `CLAUDE.md` gains `just eval --tag <skill>` for running one skill's cases.

## Risks

- **A run is one turn.** A skill that asks a question before writing produces no spec, and the case fails with a correct skill. The scaffolded intents leave nothing to ask, and the skill's two fallback rules cover what a run cannot ask about.
- **The pattern for R5 shows the skill read the code.** It does not show the design is right. Nothing here measures that.
- **The scaffolds hold documents written by hand.** They can drift from the format. The new test catches a document that no longer lints. It cannot catch a case that has stopped testing what its name says.
- **The suite grows.** Five cases, three runs each, with and without the plugin, is 30 runs. `just eval --tag generating-a-spec` runs this skill's three.
- **R12 and R13 cannot be shown the way they were for the first skill.** The next intent will not be on `main` while this stack waits to be merged, and `asdlc spec new` rightly refuses it. See Proof.

## Proof

- **`just check`.** The shape check reads the new skill and its cases, and the new test lints what every scaffold builds.
- **R17.** Tests in `tests/domain/test_documents.py`: a requirement with two `- replaces:` lines is a `property` finding that names the heading and the key, and one with a single line is not.
- **R1 to R11, R14, R15, R16.** `just eval --tag generating-a-spec`, three runs a case, with its report in the pull request.
- **R12.** A live session on this repository's next intent, in a copy of the repository where that intent's merge is simulated: the draft is shown, one correction is applied, and nothing is pushed before that.
- **R13.** Not shown by this plan. The skill's last step is the first skill's, word for word in what it forbids, and that one opened a pull request and stopped. This skill opening one is seen the first time it is used after the stack is merged.
