# asdlc

A Claude Code plugin implementing Anthropic's AI-native SDLC playbook. This is version 2, rebuilt on one rule: a document is accepted when it is on `main`.

## Commands

- `just check` - everything: `asdlc document check` on the example, formatting, ruff and every test. Exits non-zero on any failure. Run it before saying any change is done, and paste its result.
- `uv run asdlc requirement list --root examples/claims` - try a command against the worked example.
- `claude plugin validate .` - the plugin and marketplace manifests.

## Words

- **lint** (`asdlc document check`) judges the documents: are they well formed and consistent with each other? It reads files only.
- **guard** (`asdlc branch check`, and the hook before `git push`) judges a change: may this branch touch these files yet?
- **eval** judges the agent: does it still do the job under this configuration? Not built yet.
- **gate** means a person's decision, recorded as a merge. It is never the name of a command.
- **check** is a verb: validate without changing anything. Lint and guard are both a `check`, on different nouns.

## The command's grammar

`asdlc <noun> <verb> [target] [flags]`, as steg's command has it.

- Nouns are singular. Verbs come from a closed set: `list`, `show`, `new`, `close`, `move`, `set`, `unset`, `start`, `stop`, `check`, `watch`, `wait`. Find the verb that already means it before adding one; `hook run` is the only verb one noun owns.
- At most one positional, and it is the target. Everything else is a flag. A boolean flag is a switch.
- No aliases and no abbreviations. Never prompt.
- stdout is the result and nothing else: one record per line, tab-separated, no header. A command that succeeds with nothing to report prints nothing. Diagnostics go to stderr.
- Every command takes `-h`, `--json`, `-q`, `-v`, `--no-color`, `--no-input` and `--root`, through the `universal` decorator in `cli.py`.
- Exit status: 0 success, 1 found something wrong, 2 bad usage, 3 the target matched nothing, 4 no repository or no main, 130 interrupted.

## The loop

- An intent, its spec, its plan and its tasks are files under `intent/<slug>/`. Each is added on a branch named for it (`intent/<slug>`, `spec/<slug>`, `plan/<slug>`, `tasks/<slug>`) and accepted by a person merging that branch.
- A task is built on `task/<slug>/<task>` once its `task.md` is on `main`. A small intent is built on `change/<slug>` with its plan as the first commit.
- Documents hold what a person declared. State (in force, replaced, built; ready, claimed, in review, done) is worked out in `asdlc/domain` from the files and from git, and never written into a file.

## Layout

`asdlc/` is the package, in three layers. `tests/test_layers.py` fails when one imports what it must not.

- `asdlc/domain/` - decides. Pure functions over data: documents, requirements, lint, the guard, tasks and their state, scaffolding. Imports nothing else here, and no files, git or printing.
- `asdlc/io/` - reads files, git, GitHub (through `gh`) and a hook's stdin. Decides nothing.
- `asdlc/presentation/` - turns what the domain returned into text for a person or JSON for a hook.
- `asdlc/cli.py` - the click command. The only module that imports all three.
- `hooks/` - registers two Claude Code hooks: `asdlc hook run lint` after Claude writes a document, and `asdlc hook run guard` before Claude runs `git push`. `bin/` - puts `asdlc` on a session's PATH. `asdlc/templates/` - the four documents, shipped in the package. `examples/claims/` - a worked example the tests read.
- `tests/` - mirrors the layers. Domain tests touch no files; `test_example.py` and `test_cli.py` run on real files and a real git repository.

## Conventions

- Python 3.15, run through uv. click is the only runtime dependency.
- A new decision goes in `domain` as a function that takes data and returns data. Reading goes in `io`, wording in `presentation`.
- A hook says why it denied something, and never fails silently.
- Fix the code, not the check. Never weaken a check or a test to make it pass.
- Canadian spelling; regular hyphens, never em dashes.
