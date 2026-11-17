---
description: Turns a described problem into an intent - intent.md on its own branch, in the requester's own words, as a pull request they merge or close. Load this before starting any work bigger than a handful of tool calls, and whenever someone describes a problem, asks for a feature or a change in behaviour, or asks to write down what is wanted, even when they did not ask for a document. Without it Claude starts building straight away, writes its own solution into the problem, swaps the requester's terms for its own, and states guesses as facts. Not for a fix that fits in a handful of tool calls - do that directly.
allowed-tools: Bash(asdlc *)
---

# Capturing an intent

An intent is what someone wants, in their words, before anyone decides how to build it. It is one file, `intent/<slug>/intent.md`, on a branch of its own. It is accepted when a person merges its pull request.

You write the words. `asdlc` makes the file, its path, its frontmatter and its branch.

Work in this order.

## 1. Decide whether this needs an intent

If the request fits in a handful of tool calls, do the work and stop. A typo, a rename, a one-line fix and a question are all like this. Write no document for them.

An intent is for work where what is wanted is not settled yet: a new behaviour, a problem with more than one answer, a change several people care about.

## 2. Start the intent before asking anything

Run `asdlc intent new <slug> --title "<what is wanted, in a few words>"`.

- The slug is two to four lowercase words joined by hyphens. It names the problem, not a solution.
- Add `--author "<name>"` when the requester is not the person whose git this is.
- The command makes the branch `intent/<slug>`, records when the intent began, writes the file from its template and prints the file's path. That path starts at the repository's root, where you ran the command, not at this skill's folder.

Run it first, before any question. The time from that command to the committed `intent.md` is measured, so the clock has to start with the conversation.

Never make the file, its folder, its frontmatter or its branch by hand. If the command fails, read what it says and fix that.

## 3. Ask only what the request did not say

An intent needs four things from the requester:

- the scope: what is in, and what is out
- who and what is affected
- what must not break
- how they will judge that it worked

Ask for the ones the request left out, in one message, and wait for the answer. If the request already gives all four, ask nothing.

Never ask how to build it. When the requester says they do not know something, do not press. It becomes an open question in step 4.

## 4. Write the body

Edit the file the command wrote. Leave its frontmatter alone and replace every `<placeholder>`.

- **Problem.** Their words and their facts. Keep their names for things, their numbers and their examples. Every fact in the intent is one they gave. Add no cause, number or system they did not mention.
- **No solution of yours.** The intent says what is wrong and what should be true afterwards, never how to get there. If the requester proposed a solution, record it as their suggestion, in their words.
- **Proposed outcome.** A list. A person can say yes or no to each line once the work is done, without asking what it means. "The page is faster" cannot be judged. "A claim's status shows within 2 seconds" can, but only write a measure the requester gave. If they gave none, the measure is an open question.
- **Affected users and systems.** The people and systems they named.
- **Constraints.** One thing that must not break to a line, each starting `- `. The spec has to say how each one is met, so write each as a plain statement.
- **Open questions.** Each thing nobody knows yet is `### Q<n>: <the question>`, numbered from 1. Something the requester did not say is a question here, never a statement anywhere else. If there are none, delete the template's `### Q1:` line and leave the section empty.

`asdlc document check <slug>` prints nothing when the document is well formed. Fix whatever it prints.

## 5. Show the draft and apply corrections

Show the body in the conversation exactly as the file has it, headings and question numbers included, and ask whether it says what they mean. What they read is what gets committed, so do not reword or reformat it for the conversation. Change what they correct, using their wording, and show it again.

Commit nothing and push nothing until they say it is right.

## 6. Commit, push, open the pull request, and stop

When they accept the draft:

1. Commit `intent/<slug>/intent.md` and nothing else. The subject is `Intent: <title>`.
2. Run `asdlc branch check`. It prints nothing when the branch changes only that file. If it prints anything, undo the other changes.
3. Push the branch and open a pull request against `main`, titled `Intent: <title>`.
4. Give the requester the pull request's link and stop.

Never merge it, and never approve it. Merging is how a person accepts the intent, and that decision is theirs. Do not start the spec: it waits for the merge.
