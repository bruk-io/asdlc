# Plan: a justfile with the standard entrypoints

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md)
- Status: draft. Merging this file, after the owner approves it in session, starts the build.
- Delivers: R13 (each check tier is one command that exits non-zero on failure), R21 (the released version builds the next one in a worktree)

Setting the project up today is a list of eight manual steps in `docs/guide.md`, and running its checks means knowing four script paths. A `justfile` at the root gives both a name: `just setup` once, then the same few commands a contributor or a hook can call.

The owner asked for "my standard entrypoints" and the repository does not record them. The names below come from the ones the philosophy plugin already uses (`just check`, `just test-changed`, `just lint`) plus what this repository needs; the owner should correct any that differ.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `justfile` | yes | The recipes below. Each calls a script that already exists, so there is one definition of what a check is | R13 |
| `tests/test_justfile.py` | yes | The recipe names are exactly the ones listed here; every `./scripts/...` a recipe calls exists and is executable; `just --list` and `just --dry-run check` succeed when `just` is installed and are skipped when it is not | R13 |
| `README.md`, `docs/guide.md` | no | "Install" starts with `just setup`, with how to install `just` itself; the manual steps stay as what the recipe does | - |
| `CHANGELOG.md` | no | One line | - |
| `plan/just-entrypoints.md` | yes | This plan | R13 |

## The recipes

| Recipe | What it does |
|---|---|
| `just` | Lists the recipes |
| `just setup` | Idempotent, prints each thing it does or finds. Checks `git`, `uv` and `gh`; runs `uv python install 3.15`; installs Backlog.md 1.55.2 with `npm` unless that version or a newer one is there; links `asdlc` and `asdlc-plugin` into `~/.local/bin`; then runs `asdlc doctor`. It never sets your identity or signs you in: it says the command to run |
| `just check` | `./scripts/check`: artefacts, conformance, tests, and every eval case's reference and null runs |
| `just test` | The unit tests alone |
| `just artefacts` | The artefact checks alone |
| `just conformance` | The playbook conformance check alone |
| `just validate` | `scripts/eval validate`: every case's reference and null runs, no model calls |
| `just audit` | `scripts/history_audit.py --report`, the history against its rules |
| `just doctor` | `asdlc doctor` |
| `just try` | A worktree of the current commit under `.worktrees/` and the command to load the plugin from it (`CLAUDE.md`: never from the working copy) |
| `just eval ...` | Passes its arguments to `scripts/eval`. A separate `just gate` and `just eval-run` are not added: both spend tokens, so a person types them with the full command, which says so |

## Order of work

1. Write the justfile and run every recipe that spends nothing, with `just` installed through `uv tool install rust-just` here.
2. Write the test and the doc lines.
3. Run `./scripts/check`, and open the pull request.

## Risks

- **A recipe drifts from the script it wraps.** Low. Each is one line calling the script; the test checks the script exists.
- **`setup` changes a machine.** Medium. It installs only Backlog.md and a Python version, both named in the guide already, links two scripts into a user directory, and asks before overwriting a link that points elsewhere. It does not touch git config, `gh` login or Claude Code settings.
- **`just` becomes another thing to install.** Low. It is one binary; the manual steps in the guide still work without it.
- **My guess at "standard" is wrong.** Medium. The recipes are cheap to rename, and the test pins the list so a rename is visible in review.

## Proof

- Every recipe that spends nothing runs here and prints what it did; `just check` exits 0 and its output is pasted in the pull request.
- `just setup` run twice on this machine changes nothing the second time.
- `./scripts/check` passes. No file under `evals/` changes (R23).
