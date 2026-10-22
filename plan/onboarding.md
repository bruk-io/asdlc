# Plan: onboarding a code repository by generating its plugin in the tasks repository

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R11 (a skill holds one policy; what must always hold is a check), R12 (agents get the same conventions in every worktree), R13 (one verified command per check tier)

The tasks-repository change (#17) defined the per-repository plugin (`docs/repo-plugins.md`) and the rule loader that delivers its rules, but nothing makes one. This change adds onboarding: the first time a task's repository has no `plugins/<slug>/` in the tasks repository, the orchestrator (PR 2a) runs the `onboard-repo` skill. The skill holds the judgement (which commands, which layers, what each layer's rule says, how the repository tests); a new script, `scripts/asdlc-plugin`, holds everything deterministic: where the plugin goes, its skeleton, proving each command by running it, checking the result against the format, and publishing it to the tasks repository's `main`.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc-plugin` | yes | Subcommands `status`, `scaffold`, `verify-command`, `check`, `publish`. Pure functions for the skeleton, the marketplace entry, writing `verified` into `commands.toml`, and every check finding; a thin shell for git, files and subprocesses. Reuses `scripts/asdlc` (loaded by path, not edited) for the board lookup, the board lock, hooks-off git, push outcomes and backoff, and `hooks/load_rules.py` for rule and glob parsing, so the check reads rules exactly as the loader does | R12, R13 |
| `skills/onboard-repo/SKILL.md` | yes | The onboarding procedure: status, scaffold, find and prove the commands, map the layers from the code, one rule per layer, a testing rule for the repository's language, a skill only for a real multi-step procedure, the authoring kit when the session has it, then check, publish and the task notes | R11, R12 |
| `docs/repo-plugins.md` | no | Additive: a rule may name its layer with `layer: <name>` frontmatter, and must then use that layer's globs; how a plugin is onboarded and published; a table with `needs` may stay unverified | R12 |
| `tests/test_asdlc_plugin.py` | yes | The logic (skeleton, marketplace merge, `verified` writer, every check finding) and the script against real git repositories in temporary folders: a tasks repository with a bare `origin`, a fake code repository whose build, test and lint are trivial shell commands | R12, R13 |
| `README.md` | no | A short "Onboarding a repository" section | - |
| `plan/onboarding.md` | yes | This plan | - |

## Order of work

1. The pure logic and its unit tests: the skeleton files for a slug, the marketplace entry merged into any marketplace text, `with_verified` (writes one table's date and proves with `tomllib` that nothing else changed), and the check findings over plain data.
2. The shell: board lookup, the onboarding worktree, `status` and `scaffold`, tested against real repositories, including that a second `scaffold` overwrites nothing.
3. `verify-command`: run in a clean checkout at `origin`'s default branch (the clone, or a kept worktree beside it), write the date on success only, refuse a command that changes tracked files.
4. `check` with `--repo` (layers and rules must match files the repository has), and `claude plugin validate` when the CLI is there.
5. `publish`: build the commit on top of `origin/main` with a temporary index, push with every hook off, retry on a rejected push, refuse on findings or when someone else published the same plugin meanwhile; bring the board clone up to date and remove the worktree.
6. The skill, written with the authoring kit and audited by its auditor agent.
7. The demonstration on a small sample repository, the README section, `./scripts/check`.

## Risks

- **A dirty board clone stops every `asdlc` command on the machine.** `asdlc` refuses a board with uncommitted changes to tracked files, and the marketplace file is tracked. So onboarding never edits the board clone: `scaffold` opens a detached git worktree of the tasks repository at `<board>.worktrees/plugin-<slug>`, from `origin/main`, and every edit, verification and check happens there. Claims and heartbeats keep working while an agent onboards.
- **Two repositories onboarded at once both change `marketplace.json`.** A rebase would conflict on the JSON. `publish` doesn't rebase: on every attempt it starts from the freshly fetched `origin/main`, adds this plugin's folder and merges this plugin's entry into origin's marketplace as data, so concurrent onboardings of different repositories never conflict. A rejected push is retried with `asdlc`'s capped attempts and backoff.
- **Two machines onboard the same repository at once.** The second `publish` sees that `plugins/<slug>/` on `origin/main` differs from what its worktree started from and refuses, naming both, rather than overwrite the other's work.
- **A command verified somewhere it can't pass elsewhere.** `verify-command` runs only in a checkout with no uncommitted changes to tracked files whose `HEAD` is `origin`'s default branch, which is what `docs/repo-plugins.md` says `verified` means; it refuses a command that changes tracked files, since a check must not change the code. The kept verification worktree carries untracked files (installed dependencies) between runs, as a developer's checkout does; a command that passes only because of something left there from an earlier, different command is the residual risk, and `build` is verified first for that reason.
- **A wrong layer map misleads every later worker.** `check --repo` refuses a layer or rule whose globs match no tracked file, a layer shadowed entirely by earlier ones, a layer with no rule (the loader only names a layer through a repository rule), and a layer rule whose globs differ from its layer's. The skill says to map only what the code shows.
- **PR 2a edits `scripts/asdlc` in parallel.** This change doesn't edit it, but loads it by path and uses some of its private helpers (`_locked`, `_require_ready`, `_catch_up`, `_board_git`). A rename there breaks `asdlc-plugin`, and the tests here catch it at merge.

## Departures from the brief

- Onboarding works in a worktree of the tasks repository, not its main clone (first risk above). `scaffold` opens it; `verify-command` writes to it; `check` reads it when it exists, else the published plugin in the board clone; `publish` pushes from it, updates the board clone so the rule loader sees the plugin at once, and removes it.
- `publish` rebuilds its commit on `origin/main` on each attempt instead of rebasing (second risk above). The fetch, the capped attempts, the backoff, hooks off and `--no-verify` are `asdlc`'s.
- `verify-command` runs only on a checkout with no uncommitted changes at `origin`'s default branch, because that is what `verified` means in `docs/repo-plugins.md`. When the clone isn't one, it makes and keeps a detached worktree beside it, `<repo>.worktrees/asdlc-verify`, reset on every run, so what `build` installs is there for `test` and the clone is never touched. It refuses a command that changes tracked files. On failure it leaves `commands.toml` exactly as it was, so an earlier `verified` date stays, as the format says.
- `check` and `publish` find the tasks repository through `--repo` when it is given, as the other subcommands do, so the skill never needs `--board`.
- `publish` prints a record of what it published (commit, commands and dates, layers, rules, skills) for the task's notes, so the skill appends the toolchain's account instead of assembling its own. This, the kept verification worktree and a shorter skill came from the authoring kit's auditor, run on the skill and the demonstration plugin.
- The auditor was run through the headless CLI (`claude -p --agent authoring-kit:authoring-auditor`), since this build ran as a subagent without the Agent tool.
- The format gains `layer: <name>` in a rule's frontmatter, so "every layer named in rules exists" has something to check. The loader ignores the key.
- `check` refuses any unverified command except a table with `needs`, which the format's own example leaves unverified because it can't run on every machine.
- `check` also refuses: a layer with no rule, a rule over 2,500 characters (a quarter of the loader's shared cap), a `{plugin_root}` path that doesn't exist, a skill whose `name` isn't its folder, and no `rules/testing-*.md`. With `--repo`, globs that match no file.
- `hooks/hooks.json` is not changed: nothing here needs a hook. The orchestrator calls the skill.

## Proof

- `./scripts/check` passes, including `tests/test_asdlc_plugin.py`.
- The demonstration: a small Python repository with three layers is scaffolded, filled, verified, checked and published to a tasks repository with a bare `origin`; then `hooks/load_rules.py`, given a PostToolUse payload for a file in the domain layer, returns that repository's domain rule naming the `domain` layer. The output is in the pull request description.
- `claude plugin validate` passes on the published plugin and on the tasks repository.
