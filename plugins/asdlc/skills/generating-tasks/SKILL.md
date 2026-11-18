---
description: Cuts an accepted plan into its tasks - a task.md for each step on the branch tasks/<slug>, as a pull request a person merges or closes - each with a size, what it depends on, and enough to build from alone. Load this before cutting, splitting, sizing or resizing the tasks of a plan, and when someone asks for the tasks of an intent. Without it Claude cuts tasks before the plan is merged, folds steps together or splits them for no reason, sizes in days, makes one task wait for another because they share a file, types the frontmatter by hand, and cuts tasks for a plan that still has a step with an open product question.
allowed-tools: Bash(asdlc *)
---

# Generating tasks

A task is one piece of an accepted plan, built later on a branch of its own by someone who is given the task and nothing else. It is `intent/<slug>/tasks/<nn>-<name>/task.md` on the branch `tasks/<slug>`, and it is accepted when a person merges the pull request that holds a plan's tasks. Tasks are cut only after their plan is on `main`.

You decide what is cut and write the words. `asdlc` makes the branch, each file, its path and its frontmatter. Never type frontmatter and never edit it.

Two requests need no branch, so settle them before you start:

- **Which tasks exist, or where they stand.** Run `asdlc task list <slug>` and answer from it. Start the branch only when the person wants tasks cut.
- **Resizing a task that is already on `main`.** Say that a size records what was known when the task was accepted, and change nothing. What was learned goes into the next sizing.

Otherwise, work in this order.

## 1. Start the branch with the command

Run `asdlc branch new tasks/<slug>`. It makes the branch from `main`, so what you read next is what was accepted.

- **It says the plan is not on `main` yet.** Stop. Tell the person which pull request has to be merged first, and do nothing else. Never make a file or the branch by hand, and never merge the plan yourself.
- **It says the branch already exists.** The branch is left from an earlier pass. Run `git rev-list --count main..tasks/<slug>`.
  - It prints 0: `main` holds everything on the branch. Switch to `main` if you are on the branch, delete it with `git branch -d tasks/<slug>`, and run the command again.
  - It prints anything else: stop. Say the branch holds commits `main` does not, and that the tasks can be asked for again once its pull request is merged and `main` is up to date, or it is closed and the branch deleted.
  - Never use `git branch -d` as the test. It also deletes a branch that is merged only to its own upstream, such as one with an open pull request.

## 2. Read what is accepted

Read `intent/<slug>/intent.md`, `intent/<slug>/spec.md` and `intent/<slug>/plan.md`, all of each, and the files the plan lists. Run `asdlc task list <slug>` to see which tasks exist and which are done. When a task that is done is a spike, read its answer from the file its "Done when" names.

## 3. Decide what each step gets

Go through the plan's steps in order. Each step is one of three things:

- **Handed over**: the plan says `- intent: <child>` under it. It gets no task and holds nothing up, even when its text still says it waits on an area of concern.
- **Waits**: it has an open product question and is not handed over. That is so when the plan says the step waits on an area of concern in the spec, or when you cannot write "What to build" without deciding what the product does. In the second case write the question out, so the person can judge whether it is one. A question about how to build something is an unknown, not a product question.
- **Specified**: any other step. It gets a task.

**When any step waits, cut nothing for this plan.** Name each step that waits and its question. Say what has to be on `main` first, with the commands: a child intent started with `asdlc intent new <child> --parent <slug>`, and the plan's step saying `- intent: <child>`, changed on `plan/<slug>`. Then run `git switch main` and `git branch -d tasks/<slug>`, so no branch is left behind, and stop.

**One task for each specified step.** A plan that could be built in a single pass still gives a task for each step, and a plan with one step gives one task. Never fold two steps into one task. Independent work inside a step is not a reason to split it. Only size and unknowns are.

For each specified step, decide three things.

**Its size**, in story points, from this table:

| Size | Meaning |
|---|---|
| 1 | A trivial change with no unknowns. Whoever builds it knows exactly what to change and where. |
| 2 | A small, well-understood change. It may touch a few places or need a simple test, with no open questions. |
| 3 | A typical task. The approach is clear, and there is real work in building and testing it. |
| 5 | A large task with some complexity or uncertainty, such as several moving parts or a dependency outside the repository. Check whether it can be split before cutting it. |
| 8 | The maximum, and a warning sign. It usually hides unknowns or is more than one task. Try to split it first. If it cannot be split, the risk is talked through in the task's own plan. |

A size is by complexity, unknowns and risk. Give the reason for each size in those terms. Never give a size, or a reason for one, in hours, days or weeks.

**Whether it is split.** Every piece of a split step is cut from that step and has its number.

- **Bigger than one 8.** It is not a task yet. Split it into tasks that each fit the table.
- **A 5 or an 8.** Try to split it before you cut it. When you do not, say why not. Once you are splitting one, you may split it along its independent work.
- **Unknowns dominate, and the rest can be sized with confidence without the answer.** Put the unknown in a first slice. Cut the other pieces now, each with a size, and each depends on the first slice.
- **Unknowns dominate, and the rest cannot be sized until the unknown is answered.** Cut a spike, and nothing else from that step. Its title starts with "Spike:". The rest of the step is cut and sized after the spike is done, when the person asks for the tasks again.

**What it depends on.** A task names another under `depends` only when it needs what that one builds. Read the plan's "Files that change" and each step's text to see what overlaps. That is best effort: two tasks that change the same file do not depend on each other for that reason, and no list of files goes on a task. One exception: a task of another step that needs the work behind a spike is cut now, depends on the spike, and says in its body that it also waits for the tasks cut after the spike.

**Asked again for a plan that already has tasks**, cut only for a specified step with no task, or whose tasks are all spikes that are done. Read each spike's answer before you size anything. When an answer leaves the rest still impossible to size, cut another spike. Change no task that exists, and cut no second task for a step that has one. When there is nothing to cut, say why, and leave no branch behind as above.

## 4. Cut each task with the command

Run this once for each task, in the order they would be built:

`asdlc task new <slug>/<nn>-<name> --step <n> --size <s> --title "<what gets built>"`

- `<nn>` is two digits counting from 01. On a later pass it goes on from the highest number on `main`.
- Add `--depends <nn>-<name>` before `--title`, once for each task it depends on. It takes the other task's folder name alone, with no slug in front.

The command writes the file from its template and prints its path. That path starts at the repository's root, where you ran the command, not at this skill's folder. `step` and `delivers` come from the plan's step, and `size` and `depends` from your flags.

## 5. Write each body

Edit each file the command wrote. Leave its frontmatter alone and replace every `<placeholder>`.

- **What to build.** Name the files, the functions and the plan's step. Someone who has the repository and this task, and never saw the conversation, has to be able to start.
  - A piece of a split step, and a spike, says which part of the step it is, because its `delivers` is the whole step's.
  - A 5 or an 8 says what makes it one.
  - A spike's "What to build" is the question, and says the rest of the step is cut once it is answered.
  - A task of size 8 says its first commit is a plan of its own, started with `asdlc plan new <slug>/<task>`, and names the risk that plan talks through.
- **Done when.** Each line is one a reviewer can answer yes or no to.
  - A spike's names the file where the answer is written. That file is outside `intent/`, because a task's branch may add no other document.
  - A task of size 8 has its own plan as a line.
- Use no heading that starts `### R`, `### Q`, `### C` or `### Step` followed by a number. Lint reads those as cited headings, and a task has none.

**To change a task's step, size, `depends` or name**, remove the file, run `asdlc task new` again with the right flags, and put the body back. Cut again, the same way, any task whose `depends` named a task you renamed.

## 6. Check it

Run `asdlc document check <slug>`. It prints nothing when the tasks are well formed and every step is accounted for. A `heading` finding on a task is about its body, and is fixed in the body. Anything else it prints about a task is about its frontmatter or about a step with no task, and is fixed by cutting again as step 5 says.

## 7. Show the draft and apply corrections

The person sees what you write, not what a tool printed. Reading a file with a tool does not show it to them. So write the draft out, in one message:

- every task's file in full, as it is on disk: its path, then the whole file in a fenced block, frontmatter included. The frontmatter shows its step, its size and what it depends on. Do not summarise a body, shorten it or reword it. The person is accepting the words in the file, so the conversation has to show those words;
- one line for each step of the plan:
  - the task or tasks cut from it, with their sizes and the reason for each size;
  - for a split step, why it was split;
  - for a 5 or an 8, why it was not split;
  - for a handed-over step, its child intent;
  - for a step with a spike, that the rest is cut after it.

Ask whether it is right. Change what the person corrects and show it again.

Commit nothing and push nothing until they say it is right.

## 8. Commit, push, open the pull request, and stop

When they accept the draft:

1. Commit the new `task.md` files and nothing else. The subject is `Tasks: <the intent's title>`.
2. Run `asdlc branch check`. It prints nothing when the branch changes only those files. If it prints anything, undo the other changes.
3. Push the branch and open a pull request against `main`, titled `Tasks: <the intent's title>`, with the line for each step as its description.
4. Give the person the pull request's link and stop.

Never merge it, and never approve it. Merging is how a person accepts the tasks. Do not start building any task: that waits for the merge.
