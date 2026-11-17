---
description: Turns an accepted spec into its plan - plan.md on its own branch, as a pull request a person merges or closes - with the files that change, an order of work whose steps say which requirements they deliver, the risks, and the proof for each requirement. Load this before writing, drafting or revising the plan for an intent, and when someone asks how an accepted spec will be built or in what order. Without it Claude plans before the spec is merged, lists files that do not exist, leaves a requirement no step delivers, decides questions the spec deliberately left open, and writes steps only someone who saw the conversation could follow.
allowed-tools: Bash(asdlc *)
---

# Generating a plan

A plan says how an accepted spec gets built: which files change, in what order, what could go wrong, and how each requirement will be shown to be met. It is `intent/<slug>/plan.md` on the branch `plan/<slug>`, and it is accepted when a person merges its pull request. It is written only after its spec is on `main`.

You write the words. `asdlc` makes the file, its path, its frontmatter and its branch.

Work in this order.

## 1. Start the plan with the command

Run `asdlc plan new <slug>`. It makes the branch `plan/<slug>`, writes the file from its template and prints the file's path. That path starts at the repository's root, where you ran the command, not at this skill's folder.

When the command says the spec is not on `main` yet, stop. Tell the person which pull request has to be merged first, and do nothing else. A plan is built on an accepted spec, and the merge is the acceptance. Never make the file or the branch by hand, never merge the spec yourself, and never write the plan somewhere else to get round it.

## 2. Read what is accepted

Read `intent/<slug>/intent.md` and `intent/<slug>/spec.md`, all of both. Note each requirement, each area of concern, and each question the spec carried.

## 3. Read the code

Read every file the spec's design names, and the tests that cover them. Find out how this repository runs its checks. The plan names files that are there and commands that work, so look before you write either.

## 4. Write the body

Edit the file the command wrote. Leave its frontmatter alone and replace every `<placeholder>`.

- **Files that change.** One `- path` to a line, each from the repository's root. A file that exists is one you have read, and has nothing after its path. A file that does not exist yet has `(new)` after it. List the tests too, and the files of a step that waits. Leave out a file the work reads and does not change.
- **Order of work.** One `### Step <n>: <one piece of the work>` each, numbered from 1, in the order they will be built.
  - A step that delivers requirements has `- delivers: R1, R2` on the line under its heading: one line, the ids separated by commas.
  - Every requirement in the spec is on some step's `- delivers:` line.
  - A step may be groundwork that delivers no requirement by itself. It has no `- delivers:` line, and its text says what it prepares and which later step needs it.
  - Under each heading, say what changes and in which files. Name the functions, the files and the commands. Someone who has the repository and this plan, and never saw the conversation, has to be able to start on any step.
- **A step that waits on a carried question.** When a requirement cannot be built until a question the spec carried is answered, keep the step and its `- delivers:` line. Say which area of concern it waits on, by its number, and put it after the steps that do not wait. Do not decide the question, and do not plan the work as if it were decided. Write `- intent: <child>` on a step only when that child intent is already on `main`.
- **Risks.** What could break, and which step is the riskiest. Name each area of concern in the spec that the work can run into, by its number, `C<n>`, so a reader can find it there.
- **Proof.** For each requirement, by its id, the check that will show it is met: a test and the file it is in, a command and what it prints, or what a person looks at.

## 5. Check it

Run `asdlc document check <slug>`. It prints nothing when the plan is well formed and every requirement is delivered. Fix whatever it prints.

## 6. Show the draft and apply corrections

Show the body in the conversation exactly as the file has it, and ask whether it is right. Point out each step that waits on a concern. Change what the person corrects and show it again.

Commit nothing and push nothing until they say it is right.

## 7. Commit, push, open the pull request, and stop

When they accept the draft:

1. Commit `intent/<slug>/plan.md` and nothing else. The subject is `Plan: <title>`.
2. Run `asdlc branch check`. It prints nothing when the branch changes only that file. If it prints anything, undo the other changes.
3. Push the branch and open a pull request against `main`, titled `Plan: <title>`.
4. Give the person the pull request's link and stop.

Never merge it, and never approve it. Merging is how a person accepts the plan. Do not cut tasks and do not start building: both wait for the merge.
