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
- area: freshness
```

`R` is a requirement, `Q` an open question, `C` an area of concern, `Step` a plan step. A requirement's id is `<slug>.R<n>` and is never reused. A later spec ends an earlier requirement with `- replaces:`; the earlier spec is never edited.

## Commands

```
asdlc <noun> <verb> [target] [flags]
```

The grammar is the one steg's command uses: a singular noun, a verb from a closed set, at most one positional (the target), and everything else a flag. `asdlc` alone lists the nouns, and `asdlc <noun>` lists its verbs.

| Command | Target | What it does |
|---|---|---|
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
- **A list is one record per line, tab-separated,** with no header: `requirement list` prints id, state, area, title.
- **`--json` is one array for a list and one object for `show`.**

| Status | Meaning |
|---|---|
| 0 | Success |
| 1 | The command ran and found something wrong |
| 2 | Bad usage |
| 3 | The target matched nothing |
| 4 | No git repository, or no `main` to compare with |
| 130 | Interrupted |

Lint judges the documents and reads only files. The guard judges a change: the branch, the files it touched and what is on `main`. Neither runs a model, and both give the same answer every time. A gate, in this project, is a person's decision recorded as a merge; the guard is what stops work getting ahead of one.

Try them on the worked example: `uv run asdlc requirement list --all --root examples/claims`.

## Install

```
/plugin install asdlc --marketplace bruk-io/asdlc
```

The plugin puts `asdlc` on a session's `PATH` and registers two Claude Code hooks: lint after Claude writes a document, and the guard before Claude runs `git push`. They run the package through uv, which fetches Python 3.15 and click the first time.

The Claude Code hooks cover agents. To cover pushes you make by hand as well, install the command for your own terminal and add the git hook:

```
uv tool install git+https://github.com/bruk-io/asdlc
asdlc hook new pre-push
```

## When each thing runs

| When | What runs | Why there |
|---|---|---|
| Starting a branch (`asdlc branch new`) | The prerequisite check | Stops work before it begins on a document that is not merged |
| After Claude writes a document | Lint, as a Claude Code hook | The model fixes it in the same turn |
| Before Claude runs `git push` | The guard, as a Claude Code hook | Sees every committed change however it was written, and tells Claude which files and why |
| Before a push by hand | The guard, as a git `pre-push` hook, if you install it | Covers people |
| On the pull request | Lint and the guard | The one that cannot be skipped. Not set up yet |

## Code

`asdlc/` is a Python package in three layers: `domain` decides, `io` reads files and git, `presentation` words the answer, and `cli.py` wires them. `just check` runs `asdlc document check` on the example, formatting, ruff and the tests.

## What is built, and what is not

Built: the document format and its lint, requirements and lineage, the guard as one function behind `asdlc branch check` and the hook before a push, lint after each document edit, the four templates, a worked example.

Not built yet:

- **Skills.** Capturing an intent, writing a spec, planning, sizing and cutting tasks are done by hand from the templates.
- **"Built" from git.** `requirement list` shows a requirement as built only when told which tasks have merged. Nothing reads that from git yet, so the command never shows it.
- **Task state.** Claimed, in review and done are meant to be read from branches and pull requests. There is no `asdlc task list`.
- **The measures.** Nothing reads merge commits or pull requests yet.
- **The required check in CI**, CODEOWNERS and branch protection. `asdlc branch check` is the command a workflow would run.
- **Commit order.** The guard judges which files a branch changed, not that a plan was committed before the code.
- **Evals.** Replaying a saved task under the plugin and scoring the result. Nothing of it exists yet.
- **Review and releases.** Version 1 had both, and an eval suite. They are on `main` and not carried over.
