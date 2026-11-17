---
kind: spec
---
# Spec: a skill that generates a plan

## Requirements

R1 to R14 describe one skill. "The skill does X" means Claude does X in the conversation with the skill loaded. "The plan" is the `plan.md` the skill wrote. This intent creates no subagent, and changes nothing in the `asdlc` package.

### R1: The plugin has a skill, `generating-a-plan`, that loads when someone asks for the plan of an intent

It loads on a plain request. Nobody has to name it.

### R2: The skill starts a plan with `asdlc plan new` and writes only its body

The path, the branch name and the frontmatter are the command's. Claude does not type them.

### R3: The skill writes no plan for an intent whose spec is not on `main`

`asdlc plan new` refuses. The skill says which merge it waits for, and makes no file and no branch by hand.

### R4: Every file the plan lists as existing is in the repository

A file under "Files that change" with no "(new)" after it is one the repository has. One that does not exist yet is marked "(new)".

### R5: A step that delivers a requirement says which, and a step that delivers none says what it prepares

A step that delivers has a `- delivers:` line naming each requirement of the spec it delivers. A step may be groundwork, as "Wire into the portal nav" is in the course's own plan. It has no `- delivers:` line, and its text says what it prepares and which later step needs it.

### R6: Every requirement in the spec is delivered by some step in the plan

### R7: The plan's risks name each area of concern in the spec that a step can run into

By its number, `C<n>`, so a reader can find it in the spec.

### R8: The plan's proof names, for each requirement in the spec, the check that will show it is met

### R9: Each step says what changes and in which files, without leaning on the conversation

Someone who has the repository and the plan, and never saw the conversation, can start on any step.

### R10: The plan answers no question the spec carried

A step that depends on a carried question names the area of concern it waits on. The plan does not decide the question.

### R11: The skill shows the draft and applies corrections before anything is pushed

### R12: The skill opens a pull request and never merges it

### R13: The plan's branch changes no file but its `plan.md`

### R14: `asdlc document check` is clean on a plan the skill wrote

### R15: The skill has an eval case where it must act and one where it must stay out

`just check` already fails without them.

## Design

### The skill

`plugins/asdlc/skills/generating-a-plan/SKILL.md` (new) (R1). It is a skill for the reason the first two are: a plan is written with the person who will accept it. It follows `plugins/asdlc/skills/generating-a-spec/SKILL.md` step for step, so the three skills read alike.

With the skill loaded, Claude works in this order:

1. Run `asdlc plan new <slug>` (R2). When it refuses because the spec is not on `main`, say which merge the plan waits for and stop (R3).
2. Read `intent.md` and `spec.md`, all of both. Note each requirement, each area of concern and each question the spec carried.
3. Read the code the spec's design names, and check that each file the plan will list as existing is there (R4).
4. Write the body:
   - "Files that change", one path to a line, with "(new)" after a file that does not exist yet (R4);
   - "Order of work" as steps, each with `- delivers:` or, for groundwork, a line of text saying what it prepares (R5), together delivering every requirement (R6), and each saying what changes and where (R9);
   - a step that depends on a carried question names its concern and decides nothing (R10);
   - "Risks", naming each concern in the spec the work can run into (R7), and the riskiest step;
   - "Proof", with the check for each requirement (R8).
5. Run `asdlc document check <slug>` and fix what it prints (R14).
6. Show the draft and apply what the requester corrects (R11).
7. Commit `plan.md` alone, run `asdlc branch check`, push, open the pull request, and stop (R12, R13).

The skill writes the intent's plan only. A task's own plan (`asdlc plan new <slug>/<task>`) belongs to building, which the intent leaves to a later one.

Step 4 follows what C1 and C2 propose. If their owner decides otherwise, the design changes there and R10 is the requirement to revisit.

### What the command already does

Nothing in `src/asdlc` changes. Read in `src/asdlc/cli.py` and `src/asdlc/domain/guard.py`:

- `plan new <slug>` makes `plan/<slug>` from `main`, and refuses with "intent/<slug>/spec.md is not on main yet" when the spec is not merged (R3).
- It writes `intent/<slug>/plan.md` from `src/asdlc/templates/plan.md` with its frontmatter filled in (R2).
- The guard allows `plan/<slug>` to change only `intent/<slug>/plan.md` (R13).

Lint already has the `delivers` rule (a step delivers a requirement no spec has), the `coverage` rule (R6), the `child` rule and the `files` rule (a plan lists no files at all).

Lint has no finding for a step with no `- delivers:` line, and that stays: a step may be groundwork (R5).

Lint does not check R4. `domain` reads no files, and a rule over every plan would fail an old plan the day a file it named is moved. R4 is the skill's to do and an eval pattern's to check.

### The eval cases

Three cases under `plugins/asdlc/evals/` (each a new `case.yaml` and `scaffold.sh`), in the format the spec skill's cases use. Each scaffold builds a repository with its documents already in git, so graders open `intent/<slug>/plan.md` by its path and read the file.

- `plan-from-an-accepted-spec` acts. `main` holds an intent and its spec, with three requirements and one area of concern the work runs into, and a small module the spec's design names. Patterns check that `asdlc plan new` ran, that only `plan.md` was created (R2, R13), that the planted module is listed without "(new)" and that every path listed without "(new)" is one the scaffold made (R4), that every `- delivers:` line names a requirement of the spec (R5), that each of the three requirements is on a `- delivers:` line (R6) and under "Proof" (R8), that "Risks" names the concern (R7), that no placeholder from the template is left (R14), and that nothing was pushed. A judge checks R9, and that a step with no `- delivers:` line says what it prepares (R5).
- `plan-with-a-carried-question` acts. The spec carried one question to an area of concern, and one of its requirements cannot be built until it is answered. Patterns check that "Risks" names that concern and that the step delivering that requirement names it too (R7, R10). A judge checks that the plan does not decide the question (R10).
- `plan-waits-for-the-merge` stays out. The spec is on the branch `spec/<slug>` and not on `main`. Patterns check that no `plan.md` was created, that no `plan/` branch was made by hand, that Claude merged nothing, and that the answer says the spec has to be merged first (R3).

`tests/test_evals.py` needs no change: it already finds every skill and case, and lints what each scaffold builds. `README.md` gains the skill.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| Claude never merges. Accepting a plan stays a person's decision. | R12. The skill stops once the pull request is open. |
| The skill writes the prose only. The path, the branch name and the frontmatter come from `asdlc plan new`. | R2. |
| The branch changes only `plan.md`, so the guard stays clean. | R13. |
| A plan is not started before its spec is on `main`. | R3. The command already refuses, and the skill does not work around it. |
| The layers in the package hold. | No requirement changes the package. Nothing under `src/asdlc` changes. |

## Open questions from intent

### Q1: The course makes its plan in Claude Code's plan mode and commits the approved plan as `plan.md`. Should this skill work in plan mode, or in an ordinary session?
- answer: carried

Carried to C1. The intent's constraints and the code allow either, so nothing here answers it.

### Q2: What does a plan do with a step that depends on a question the spec carried and nobody has answered?
- answer: carried

Carried to C2. The code has one mechanism, a step that hands over to a child intent, and it cannot be used on a plan's branch as things stand.

### Q3: A small intent is built on `change/<slug>` with its plan as the first commit. Should the skill write that plan too, or only the one on `plan/<slug>`?
- answer: answered

Only the one on `plan/<slug>`. This comes from the code and from the intent's own constraint. `asdlc plan new <slug>` always works on `plan/<slug>`: `_on_branch` in `src/asdlc/cli.py` switches to that branch from whichever one it is run on, `change/<slug>` included. The intent says the branch name comes from `asdlc plan new`, so the skill has no way to put a plan on `change/<slug>`. Whether an intent is small enough for a `change/` branch is sizing, which the intent leaves to a later one. That intent can give the command a way to start a change, and this skill a reason to use it.

## Areas of concern

### C1: Plan mode or an ordinary session is not decided
- owner: Bruk Habtu

This is Q1. In plan mode Claude changes nothing until the plan is approved, so `asdlc plan new` would run after the approval and the approved text would go into the file it wrote. That gives the review of the draft (R11) a built-in place. In an ordinary session the skill runs the command first and shows the draft in the conversation, as the first two skills do.

Proposed: an ordinary session. The three skills then work the same way. An eval run is one turn with nobody to approve a plan, so a skill that needs plan mode could not be measured by the cases in R15. A skill also cannot choose the mode its session is in. The cost is that this differs from the course.

### C2: A step that waits on a carried question has no clean place in a plan
- owner: Bruk Habtu

This is Q2. The template gives such a step one form: `- intent: <child>`, a handover to a child intent. Lint's `child` rule then needs that child intent to exist and to name this intent as its parent. On `plan/<slug>` the guard allows only `plan.md`, so the child intent has to be captured and merged before the plan is written. The intent wants lint clean on the plan (R14) and the branch to change only `plan.md` (R13). Both hold with a handover only if a second intent is merged first, which makes writing one plan wait on a second pull request.

Proposed, and what R10 and the design assume: the plan keeps the step, with its `- delivers:` line. The step says which area of concern it waits on. "Risks" names that concern, and the order of work puts the step after the ones that do not wait. The plan decides nothing. Whoever cuts the tasks sees a step that cannot start yet. The skill writes `- intent: <child>` only when that child intent is already on `main`.

The other way through is for the skill to stop, say that a child intent is needed, and write no plan until it is merged.

### C3: An eval run is one turn with no network
- owner: Bruk Habtu

So no case shows a correction being applied (R11) or a pull request being opened (R12). As with the first two skills, those are shown by using the skill in a live session on this repository's next plan.

### C4: Whether someone else could build from the plan is a judge's call
- owner: Bruk Habtu

R9 needs a judge, and a judge's verdict varies between runs. Each case runs three times, and no case rests on a judge alone. The spread is still not measured, so no pass mark is set here.

### C5: Only the skill checks that a listed file exists
- owner: Bruk Habtu

R4 is not a lint rule, for the reason the design gives. A plan written by hand, or by a session that did not load the skill, can list a file that is not there, and lint is clean. The eval pattern for R4 covers the skill in a scaffolded repository of a few files and nothing else.
