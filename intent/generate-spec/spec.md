---
kind: spec
---
# Spec: a skill that generates a spec

## Requirements

R1 to R15 describe one skill. "The skill does X" means Claude does X in the conversation with the skill loaded. This intent creates no subagent. R17 and R18 are its only changes to the `asdlc` package.

### R1: The plugin has a skill, `generating-a-spec`, that loads when someone asks for the spec of an intent

It loads on a plain request. Nobody has to name it.

### R2: The skill starts a spec with `asdlc spec new` and writes only its body

The path, the branch name and the frontmatter are the command's. Claude does not type them.

### R3: The skill writes no spec for an intent that is not on `main`

`asdlc spec new` refuses. The skill says which merge it waits for, and makes no file and no branch by hand.

### R4: Each requirement in the spec is one thing a person can check, yes or no

### R5: Every existing file the design names is in the repository

The design says where the change goes in the code that is already there. A file it names as existing is one the repository has, and a new one is marked as new.

### R6: Every constraint in the intent has a row that says what meets it

### R7: Every open question in the intent appears in the spec, answered or carried

### R8: A question the skill cannot answer is carried to an area of concern, not answered with a guess

An answer comes from the intent, the code or the requester. Anything else is carried.

### R9: Two things that cannot both be satisfied become an area of concern

The skill says what conflicts and may propose a way through. It does not pick one side and write the spec as if there were no conflict.

### R10: Every area of concern names an owner

### R11: A requirement that ends one in force says which one it replaces

The skill reads the requirements in force before it writes its own.

### R12: The skill shows the draft and applies corrections before anything is pushed

### R13: The skill opens a pull request and never merges it

### R14: The spec's branch changes no file but its `spec.md`

### R15: `asdlc document check` is clean on a spec the skill wrote

### R16: The skill has an eval case where it must act and one where it must stay out

`just check` already fails without them.

### R17: Lint finds a property written twice under one heading

Today the second `- replaces:` under a requirement silently wins and the first is dropped. The skill's first pilot run wrote two, lint was clean, and one of the two requirements it meant to end stayed in force.

### R18: Lint finds an area of concern that names no owner

Today a concern with no `- owner:` under its heading is clean. A later pilot run wrote its owners under the concern's text, where they are not read, and lint said nothing.

## Design

### The skill

`plugins/asdlc/skills/generating-a-spec/SKILL.md` (R1). It is a skill for the reason `capturing-intent` is: writing a spec is a conversation with the person who will accept it.

With the skill loaded, Claude works in this order:

1. Run `asdlc spec new <slug>` (R2). When it refuses because the intent is not on `main`, say which merge the spec waits for and stop (R3).
2. Read `intent.md`, then `asdlc requirement list` for what is in force (R11).
3. Read the code the intent's "Affected users and systems" names (R5).
4. Write the body:
   - one checkable requirement to a `### R<n>:` (R4), with `- replaces:` under one that ends a requirement in force (R11);
   - a design that names the files it changes (R5);
   - each constraint, copied word for word, with what meets it (R6);
   - each question, answered or carried (R7, R8);
   - each area of concern with an owner (R9, R10).
5. Run `asdlc document check <slug>` and fix what it prints (R15).
6. Show the draft and apply what the requester corrects (R12).
7. Commit, push, open the pull request, and stop (R13, R14).

### The eval cases

Three cases under `plugins/asdlc/evals/`, in the format the first skill's cases use. Each case's `scaffold.sh` builds a repository with its documents already in git, so the intent's slug is known and graders open `intent/<slug>/spec.md` by its path. They read the file itself, not what the skill says about it.

- `spec-from-an-accepted-intent` acts. An intent is on `main` with two constraints and two questions. The repository's code answers one question, and nothing answers the other. Patterns check that `asdlc spec new` ran, that only `spec.md` was created, that each constraint has a row (R6), that the first question is answered and the second carried (R7, R8), that every concern has an owner (R10), that the design names a module the intent never mentions (R5), and that nothing was pushed. A judge checks R4.
- `spec-with-a-conflict` acts. An earlier spec has a requirement in force that the new intent ends, and the new intent has two constraints that cannot both hold. Patterns check for `- replaces:` naming that requirement (R11) and for a concern that names both constraints (R9). A judge checks that the requirements do not quietly satisfy one constraint and drop the other.
- `spec-waits-for-the-merge` stays out. The intent is on its own branch and not on `main`. Patterns check that no `spec.md` was created and that no `spec/` branch was made by hand (R3).

### The two changes to the package

`items` in `src/asdlc/domain/documents.py` keeps the last value when a property is written twice under a heading. It will note the repeat, and `parse` will report it under the `property` rule (R17). A requirement ends one requirement, so the message says to write a requirement for each one that ends.

`parse` will also report a `### C<n>:` heading with no `- owner:` on the line under it, under a new `owner` rule (R18). The message says where the line goes.

Nothing else in `src/asdlc` changes. `asdlc spec new` already refuses an intent that is not on `main` and says what it waits for, and lint already has the rules behind R6 and R7.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| Claude never merges. Accepting a spec stays a person's decision. | R13. The skill stops once the pull request is open. |
| The skill writes the prose only. The path, the branch name and the frontmatter come from `asdlc spec new`. | R2. |
| The branch changes only `spec.md`, so the guard stays clean. | R14. |
| A spec is not started before its intent is on `main`. | R3. The command already refuses, and the skill does not work around it. |
| The layers in the package hold. | R17 and R18 are rules in `domain`, where lint's decisions live. Nothing in `io` or `presentation` changes. |

## Open questions from intent

### Q1: Should a spec name the policy skills it applied, the way the course's example has a "Skills applied" line, when this plugin ships no policy skills?
- answer: carried

Carried to C1. The document already has a place for them, `policies:` in the frontmatter, and lint accepts it. But the frontmatter is the command's to write, `asdlc spec new` leaves that line out, and there are no policy skills to name. So a spec written by this skill names none.

### Q2: How can an eval case show that a design fits the existing code without leaning on a judge?
- answer: answered

By planting a name. The case's repository holds a module the intent never mentions, and a design that fits has to name it. A pattern looks for that name in `spec.md` (R5). It shows the skill read the code. It does not show the design is a good one, and no pattern can.

## Areas of concern

### C1: A spec names no policy skills, where the course's spec does
- owner: Bruk Habtu

The course's prompt says to apply the skills available, so that the spec conforms to security, brand and UX policy, and its example lists them. This plugin has none. The intent that brings policy skills also has to decide how their names reach the frontmatter, since a skill may not type it.

### C2: An eval run is one turn with no network
- owner: Bruk Habtu

So no case shows a correction being applied (R12) or a pull request being opened (R13). As with the first skill, those two are proved by using the skill on this repository's next spec in a live session.

### C3: Whether a requirement can be checked is a judge's call
- owner: Bruk Habtu

R4 needs a judge, and a judge's verdict varies between runs. Each case runs three times, and no case rests on a judge alone. The spread is still not measured, so no pass mark is set here.

### C4: The skill reads the code before it writes the design, and nothing bounds that
- owner: Bruk Habtu

In the cases the repository is a handful of files. In a large one, reading enough to write a design that fits may be slow, or may miss the module that matters. Nothing here measures that.
