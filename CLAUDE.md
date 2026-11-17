# asdlc

A Claude Code plugin implementing Anthropic's AI-native SDLC playbook. This is version 2, rebuilt on one rule: a document is accepted when it is on `main`.

## Commands

- `just check` - everything: `asdlc document check` on the example, formatting, ruff and every test. Exits non-zero on any failure. Run it before saying any change is done, and paste its result.
- `uv run asdlc requirement list --root examples/claims` - try a command against the worked example.
- `claude plugin validate .` and `claude plugin validate plugins/asdlc` - the marketplace and plugin manifests.
- `just eval` - run the plugin's eval cases with `claude plugin eval`: three runs a case, with the plugin and without it. It runs a model and spends money, so it is not part of `just check` or of CI. `just eval --tag <skill>` runs one skill's cases, and `just eval --case <name> --runs 1 --ablation none` is one cheap run of one case.

## Words

- **lint** (`asdlc document check`) judges the documents: are they well formed and consistent with each other? It reads files only.
- **guard** (`asdlc branch check`, and the hook before `git push`) judges a change: may this branch touch these files yet?
- **eval** judges the agent: does it still do the job under this configuration? Its cases are under `plugins/asdlc/evals/`, and `just eval` runs them.
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
- Documents hold what a person declared. State (in force, replaced, built; ready, claimed, in review, done) is worked out in `src/asdlc/domain` from the files and from git, and never written into a file.

## Layout

The repository is a marketplace holding one Python package and one plugin. `.claude-plugin/marketplace.json` lists the plugins under `plugins/`.

`src/asdlc/` is the package, in three layers. `tests/test_layers.py` fails when one imports what it must not.

- `src/asdlc/domain/` - decides. Pure functions over data: documents, requirements, lint, the guard, tasks and their state, scaffolding. Imports nothing else here, and no files, git or printing.
- `src/asdlc/io/` - reads files, git, GitHub (through `gh`) and a hook's stdin. Decides nothing.
- `src/asdlc/presentation/` - turns what the domain returned into text for a person or JSON for a hook.
- `src/asdlc/cli.py` - the click command. The only module that imports all three.
- `src/asdlc/templates/` - the four documents, shipped in the package. `examples/claims/` - a worked example the tests read.
- `plugins/asdlc/` - the Claude Code plugin, and everything Claude Code loads: its manifest in `.claude-plugin/plugin.json`, its skills in `skills/`, their eval cases in `evals/`, and later its agents. `hooks/hooks.json` registers three hooks: `scripts/install` when a session starts, `asdlc hook run lint` after Claude writes a document, and `asdlc hook run guard` before Claude runs `git push`.
- An installed plugin is a copy of `plugins/asdlc/` alone, without `src/`. So `scripts/install` installs the package at each session start: from the working tree in a checkout, and otherwise from the repository, once for each version of `plugin.json`. It installs into `${CLAUDE_PLUGIN_DATA}`, which the hooks call, and copies that to the session's temp folder, which goes first on `PATH`. Nothing else in the plugin may read a path above its own folder.
- In a session, the hooks and `asdlc` on `PATH` are the copy made when the session started. After editing `src/asdlc`, `uv run asdlc` runs the working tree, and a new session refreshes the copy.
- `tests/` - mirrors the layers. Domain tests touch no files; `test_example.py` and `test_cli.py` run on real files and a real git repository.

## Conventions

- Python 3.15, run through uv. click is the only runtime dependency.
- A new decision goes in `domain` as a function that takes data and returns data. Reading goes in `io`, wording in `presentation`.
- A hook says why it denied something, and never fails silently.
- A skill lands with its eval cases: one tagged with the skill's name and `acts`, one with its name and `stays-out`, and in each a grader that is a pattern and not a judge. `tests/test_evals.py` fails `just check` otherwise. Pilot a case with one run before the full three, and read what the run wrote before changing a grader. A case's `scaffold.sh` writes its documents by hand, and a test lints what each scaffold builds.
- Fix the code, not the check. Never weaken a check or a test to make it pass.
- Canadian spelling; regular hyphens, never em dashes.
