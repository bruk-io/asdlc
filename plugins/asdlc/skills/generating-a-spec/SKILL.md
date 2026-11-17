---
description: Turns an accepted intent into its spec - spec.md on its own branch, as a pull request a person merges or closes - with numbered requirements that can each be checked, a design that fits the code already there, how each of the intent's constraints is met, each of its open questions answered or carried, and areas of concern with an owner. Load this before writing, drafting or revising the spec, the requirements or the design for an intent, and when someone asks what it would take to build an accepted intent. Without it Claude starts a spec before its intent is merged, writes requirements nobody can check, answers open questions with guesses, quietly picks a side when two constraints conflict, and misses the requirement in force that the new one ends.
allowed-tools: Bash(asdlc *)
---

# Generating a spec

A spec says what must be true when an intent is built, and how. It is `intent/<slug>/spec.md` on the branch `spec/<slug>`, and it is accepted when a person merges its pull request. It is written only after its intent is on `main`.

You write the words. `asdlc` makes the file, its path, its frontmatter and its branch.

Work in this order.

## 1. Start the spec with the command

Run `asdlc spec new <slug>`. It makes the branch `spec/<slug>`, writes the file from its template and prints the file's path. That path starts at the repository's root, where you ran the command, not at this skill's folder.

When the command says the intent is not on `main` yet, stop. Tell the person which pull request has to be merged first, and do nothing else. A spec is built on an accepted intent, and the merge is the acceptance. Never make the file or the branch by hand, never merge the intent yourself, and never write the spec somewhere else to get round it.

## 2. Read what is accepted

- Read `intent/<slug>/intent.md`, all of it.
- Run `asdlc requirement list`. It prints every requirement in force, across all intents. Note each one this intent's outcomes would contradict or end.

## 3. Read the code the intent touches

The design has to fit what is there. Find the files behind what the intent's "Affected users and systems" names, and read them. Look for what already answers one of the intent's open questions.

## 4. Write the body

Edit the file the command wrote. Leave its frontmatter alone and replace every `<placeholder>`.

Look for conflicts first. Read the intent's constraints and outcomes against each other, and against the requirements in force. Two that cannot both be true as the requester wrote them are a conflict. Write its area of concern before you write a requirement, so the requirements are written knowing it.

- **Requirements.** One `### R<n>: <one thing that must be true>` each, numbered from 1. A person can answer yes or no to each once the work is built. "The page is fast" cannot be checked. "A claim's step shows in the adjuster portal" can. One thing to a requirement.
- **What it replaces.** When a requirement ends one in force, put `- replaces: <intent>.R<n>` on the line under its heading, with the id exactly as `asdlc requirement list` printed it. A requirement ends one requirement: to end two, write a requirement for each. End only what the intent's outcomes contradict, and leave the rest in force.
- **Design.** How the requirements are met in this code. Name the files it changes. A file you name as existing is one you have read. Write "(new)" after one that does not exist yet.
- **How each constraint in the intent is met.** One table row for each constraint in the intent. Copy the constraint word for word into the first cell, because lint matches on the text. The second cell names the requirement or the decision that meets it.
- **Open questions from intent.** Copy each of the intent's questions as `### Q<n>: <the question>`, keeping its number. On the next line write `- answer: answered` or `- answer: carried`, then a line saying the answer or where the question went.
  - An answer comes from the intent, the code, or the person you are working with. Say which.
  - Anything else is carried to an area of concern. A guess is not an answer, and neither is deciding the question is out of scope.
- **Areas of concern.** One `### C<n>: <what could go wrong>` each. The line directly under the heading is `- owner: <who decides>`, and the text comes after it. An owner written under the text is not read.
  - A conflict is a concern. Say which two things conflict, say why both cannot hold, and say what you would propose.
  - Do not make a conflict go away yourself. Do not assume a fact that would let both hold, such as data nobody mentioned and the code does not have. Do not read either one more narrowly than it was written. The table row for a constraint the spec does not meet says "Not met" and points at the concern.
  - Every question you carried lands here.
  - The owner is a person or a team the intent or the person named. When none fits, the owner is the intent's author, and you say so when you show the draft.
  - If there is nothing to raise, delete the template's `### C1:` lines and leave the section empty.

## 5. Check it

Run `asdlc document check <slug>`. It prints nothing when the spec is well formed and agrees with its intent. Fix whatever it prints.

## 6. Show the draft and apply corrections

Show the body in the conversation exactly as the file has it, and ask whether it is right. Point out each question you carried and each concern. Change what the person corrects and show it again.

Commit nothing and push nothing until they say it is right.

## 7. Commit, push, open the pull request, and stop

When they accept the draft:

1. Commit `intent/<slug>/spec.md` and nothing else. The subject is `Spec: <title>`.
2. Run `asdlc branch check`. It prints nothing when the branch changes only that file. If it prints anything, undo the other changes.
3. Push the branch and open a pull request against `main`, titled `Spec: <title>`.
4. Give the person the pull request's link and stop.

Never merge it, and never approve it. Merging is how a person accepts the spec. Do not start the plan: it waits for the merge.
