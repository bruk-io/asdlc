# asdlc

Anthropic's [AI-native SDLC playbook](https://academy.claude.com/courses/ai-native-sdlc-playbook) as a Claude Code plugin. Version 2 is a rebuild around one rule:

**A document is accepted when it is on `main`.**

An intent, its spec, its plan and its tasks are Markdown files in the repository. Each is added by a pull request and accepted by a person merging it. Nothing stores a status: draft, accepted, replaced and built are all read from the files and from git.

## The chain

```
intent/
  claims-status/
    intent.md            what is wanted, in the requester's words
    spec.md              numbered requirements, the design, what was decided
    plan.md              how the whole intent gets built, step by step
    tasks/
      01-status-endpoint/
        task.md          cut from a plan step; cites the requirements it delivers
      02-status-panel/
        task.md
        plan.md          only when sizing says the task needs its own
```

| Branch | Adds | Needs on `main` first |
|---|---|---|
| `intent/<slug>` | `intent.md` | nothing |
| `spec/<slug>` | `spec.md` | the intent |
| `plan/<slug>` | `plan.md` | the spec |
| `tasks/<slug>` | the `task.md` files | the plan |
| `task/<slug>/<task>` | the code, and the task's own plan | its `task.md` |
| `change/<slug>` | a small intent's plan and code together | the spec |

## What a document looks like

Flat frontmatter, then headings that other documents cite:

```markdown
---
kind: spec
policies: [pii-in-logs]
---
### R1: Status updates within 2 seconds of a change
- replaces: claims-status.R3
```

`R` is a requirement, `Q` an open question, `C` an area of concern, `Step` a plan step. A requirement's id is `<slug>.R<n>` and is never reused. A later spec ends an earlier requirement with `- replaces:`; the earlier spec is never edited.

`policies` names the policy skills applied while the spec was written, as the course's example spec has a "Skills applied" line. A policy skill is a rule of the repository that adopts asdlc, written as a skill of its own under `.claude/skills/`. This plugin ships none, and `pii-in-logs` above is an example name, not a skill that exists. Lint accepts the list and does not check that a skill of that name exists.

Lint also reads two sections, both named as the course names them:

- A plan's `## Files that change` lists the files it touches, one `- path` to a line.
- A spec's `## How each constraint in the intent is met` is a table with a row for every constraint the intent lists.

## Commands

```
asdlc <noun> <verb> [target] [flags]
```

The grammar is the one steg's command uses: a singular noun, a verb from a closed set, at most one positional (the target), and everything else a flag. `asdlc` alone lists the nouns, and `asdlc <noun>` lists its verbs.

| Command | Target | What it does |
|---|---|---|
| `asdlc intent new` | The new intent's slug | Starts an intent on its branch from the template. The branch's first commit is an empty one, so git holds when the intent began. `--author`, `--parent`, `--title` |
| `asdlc intent list`, `intent show` | none; an intent's slug | The intents and how far each has got: intent, spec, plan, tasks, built |
| `asdlc spec new` | An intent's slug | Starts its spec on its branch, once the intent is on `main` |
| `asdlc plan new` | An intent's slug, or `<slug>/<task>` | Starts the intent's plan, or a task's own plan |
| `asdlc task new` | `<slug>/<task>` | Cuts a task from a plan step. `--step`, `--size`, `--depends`; what it delivers is copied from the step |
| `asdlc task list`, `task show` | An intent's slug, or none; `<slug>/<task>` | The tasks and their state: waiting, ready, claimed, in review, done |
| `asdlc task start` | `<slug>/<task>` | Starts a ready task: moves the checkout it is run in to the task's branch, pushes it, and opens a draft pull request |
| `asdlc document check` | An intent's slug, or none for all | Lint: everything wrong in and between the documents |
| `asdlc requirement list` | none | The requirements in force. `--all` adds replaced and retired ones |
| `asdlc requirement show` | A requirement id | One requirement in full, with what it replaced and what replaced it |
| `asdlc branch new` | The new branch's name | Starts a branch from `main`, and refuses until the document it builds on is merged |
| `asdlc branch check` | A branch, or none for the current one | Guard: whether the branch changed only what its documents on `main` allow |
| `asdlc hook run` | A hook's name (`guard`, `lint`) | Runs a Claude Code hook on the tool call read from standard input |
| `asdlc hook new` | A git hook's name (`pre-push`) | Optional: installs a git hook that runs the guard for pushes made by hand |
| `asdlc version` | none | The version |

Every command takes `-h`, `--json`, `-q` (identifiers only), `-v` (diagnostics on stderr), `--no-color`, `--no-input` and `--root <folder>`.

- **stdout is the result and nothing else.** A check that finds nothing prints nothing.
- **A list is one record per line, tab-separated,** with no header: `requirement list` prints id, state, title.
- **`--json` is one array for a list and one object for `show`.**

| Status | Meaning |
|---|---|
| 0 | Success |
| 1 | The command ran and found something wrong |
| 2 | Bad usage |
| 3 | The target matched nothing |
| 4 | No git repository, or no `main` to compare with |
| 130 | Interrupted |

State is never stored. A task is claimed because its branch `task/<slug>/<task>` exists, in review because that branch has an open pull request (read through `gh`), and done because it was merged. A pull request that is a draft does not count as open here, so its task reads as claimed until the pull request is marked ready. `asdlc task show` gives the link of the task's pull request, draft or not. A requirement is built when every task that delivers it is done. This depends on pull requests being merged with a merge commit. `asdlc task list` and `asdlc task show` read which tasks exist from the remote's `main`, and fetch first. So a task on a branch that is not merged is not listed, and a task whose branch was pushed from another clone shows as claimed. When the fetch fails they say so, and read what was last fetched. A repository with no remote has its local `main` read.

Lint judges the documents and reads only files. The guard judges a change: the branch, the files it touched and what is on `main`. Neither runs a model, and both give the same answer every time. A gate, in this project, is a person's decision recorded as a merge; the guard is what stops work getting ahead of one.

Try them on the worked example: `uv run asdlc requirement list --all --root examples/claims`.

## Starting a task

`asdlc task start <slug>/<task>` starts a task that reads as ready on the remote. In order:

1. It fetches, and moves the checkout it is run in to a new branch, `task/<slug>/<task>`, made from the remote's `main`. It makes no worktree.
2. It makes an empty commit, `Start task <slug>/<task>`, so git holds when the task began.
3. It pushes the branch. The push is the claim: from then on the task reads as claimed in every clone.
4. It opens a draft pull request against `main`, and prints the branch and the pull request's link.

It starts nothing in a checkout with uncommitted changes, and nothing it can tell it could not finish: with no remote, with a `gh` that cannot reach the repository's pull requests, or with no checks on `main`. When it fails part way, it puts the checkout back where it was.

When two clones start one task at the same moment, one push makes the branch and the other start is undone and says whose pull request won. When the pull request cannot be opened, the start takes its branch off the remote again, so the task reads as ready. When the remote will not give the branch up, the start says that it is left there, and names `asdlc task start --resume` to finish it.

The checks are the command lines in `.asdlc/checks` on the remote's `main`, one to a line, with `#` for a comment. They are what a task has to pass before its pull request is marked ready. In this repository the file holds one line, `just check`. No command runs them yet, but no task is started without them.

One checkout holds one task at a time. To build tasks side by side, give each a session of its own in a worktree of its own, started with `claude --worktree <name>`, and run `asdlc task start` there.

## Install

```
/plugin install asdlc --marketplace bruk-io/asdlc
```

When a session starts, the plugin installs the `asdlc` command with uv and puts it first on the session's `PATH`. uv fetches Python 3.15, click and the command itself from this repository the first time, and again when the plugin's version changes. Two more Claude Code hooks call that command: lint after Claude writes a document, and the guard before Claude runs `git push`. If the install fails, the session says why, and so does each hook when it cannot run.

The Claude Code hooks cover agents. To cover pushes you make by hand as well, install the command for your own terminal and add the git hook:

```
uv tool install git+https://github.com/bruk-io/asdlc
asdlc hook new pre-push
```

## Skills and their evals

A skill tells Claude how to run one stage. Each lands with eval cases that judge whether Claude does the job with it.

| Skill | When it loads | What it leaves |
|---|---|---|
| `capturing-intent` | Someone describes a problem, or asks for work bigger than a handful of tool calls | `intent.md` on `intent/<slug>`, in the requester's words, as a pull request. It never merges |
| `generating-a-spec` | Someone asks for the spec, the requirements or the design of an intent | `spec.md` on `spec/<slug>`, as a pull request: checkable requirements, a design that names the code, each constraint and question dealt with, concerns with owners. It writes nothing until the intent is on `main`, and it never merges |
| `generating-a-plan` | Someone asks for the plan of an intent, or how an accepted spec will be built | `plan.md` on `plan/<slug>`, as a pull request: the files that change, steps that say which requirements they deliver, the risks, and the proof for each requirement. It writes nothing until the spec is on `main`, and it never merges |
| `generating-tasks` | Someone asks for the tasks of an intent, or to cut, split or size the work of an accepted plan | `task.md` files on `tasks/<slug>`, as a pull request: a task for each step, each with a size, what it depends on, and enough to build from alone. It cuts nothing until the plan is on `main`, nothing while a step has an open product question, and it never merges |

The cases are in `plugins/asdlc/evals/`, in the format `claude plugin eval` reads. `just eval` runs them three times each, with the plugin and without it, and writes a report under `plugins/asdlc/evals/results/`. `just eval --tag <skill>` runs one skill's cases. It runs a model, so it is not part of `just check`. `just check` does read the cases: it fails when a skill lacks a case where it must act or one where it must stay out, or when a case has no pattern grader.

## When each thing runs

| When | What runs | Why there |
|---|---|---|
| Starting a branch (`asdlc branch new`) | The prerequisite check | Stops work before it begins on a document that is not merged |
| After Claude writes a document | Lint, as a Claude Code hook | The model fixes it in the same turn |
| Before Claude runs `git push` | The guard, as a Claude Code hook | Sees every committed change however it was written, and tells Claude which files and why |
| Before a push by hand | The guard, as a git `pre-push` hook, if you install it | Covers people |
| On the pull request | Lint and the guard | The one that cannot be skipped. Not set up yet |

## Code

The repository is a marketplace with two parts. `plugins/asdlc/` is the Claude Code plugin: its manifest, its hooks and the script that installs `asdlc` when a session starts. `src/asdlc/` is a Python package in three layers: `domain` decides, `io` reads and writes files, git and GitHub, and `presentation` words the answer. `domain` and `io` import nothing from each other. `cli.py` is the app layer that joins them, and a test fails if any other module does. `just check` runs `asdlc document check` on the example, formatting, ruff and the tests.

## What is built, and what is not

Built: the document format and its lint, scaffold commands for each document, task and intent state read from git, requirements and lineage, the guard as one function behind `asdlc branch check` and the hook before a push, lint after each document edit, four templates, a worked example. Four skills, `capturing-intent`, `generating-a-spec`, `generating-a-plan` and `generating-tasks`, each with its eval cases under `plugins/asdlc/evals/`.

Not built yet:

- **The other skills.** Sizing and cutting tasks is a skill now. `asdlc task start` starts a task. The rest of building one is still done by hand: nothing runs the checks or ends the task yet, and there is no skill for it.
- **The measures.** Nothing reads merge commits or pull requests yet.
- **Making CI required.** `.github/workflows/ci.yml` runs lint, the tests and the guard on every pull request, but branch protection and `CODEOWNERS` are not set up, so nothing yet stops a merge.
- **Commit order.** The guard judges which files a branch changed, not that a plan was committed before the code.
- **Evals in CI.** The cases run by hand, with `just eval`. Nothing runs them on a pull request or on a schedule yet, and no pass mark is set.
- **Review and releases.** Version 1 had both, and an eval suite. They are on `main` and not carried over.
