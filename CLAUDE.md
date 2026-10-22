# asdlc

A Claude Code plugin implementing Anthropic's AI-native SDLC playbook. It builds itself: every change to this repository carries an approved plan.

## Commands

- `./scripts/check` - every artefact check and every test, under Python 3.15 through uv. Exits non-zero on any failure. Run it before saying any change is done, and paste its result.
- `uv run --script scripts/artefacts.py .` - the artefact checks alone.
- To try the plugin on this repository, load it from a separate worktree of a released commit (`claude --plugin-dir <that worktree>`), never from this working copy: Claude Code refuses edits inside a loaded plugin's own folder, and the released version must not edit itself (spec R21).
- `claude plugin validate .` - the plugin and marketplace manifests. Not `--strict`: it warns that this `CLAUDE.md` doesn't ship with the plugin, which is intended, since it is this repository's own.

## The loop

Each change carries its plan, `plan/<slug>.md` (files, order, risks, proof, citing requirement numbers from `spec/`), in the same pull request as the change. The owner approves the plan in the session before anything is built; the merge is the gate for both. `intent/` and `spec/` hold the accepted problems and requirements that plans cite.

If a change departs from its plan, update the plan in the same commit and say why.

Every pull request is reviewed by Claude in CI (`review.yml`) under the rules in `REVIEW.md`, both read from `main`. A review never approves; the person who merges does.

## Layout

- `skills/`, `commands/`, `hooks/` - the plugin. `templates/` - the artefact templates the skills copy.
- `scripts/` - deterministic checks. `tests/` - one `unittest` module per script and hook.
- `intent/`, `spec/`, `plan/` - this repository's own artefacts.

## Conventions

- Python 3.15, standard library only. Each script declares `requires-python = ">=3.15"` inline and runs with `uv run --script`.
- Logic takes data and returns data; files, git and stdin stay in a thin shell around it.
- A hook says why it denied something, and never fails silently.
- Fix the code, not the check. Never weaken a check or a test to make it pass.
- Canadian spelling; regular hyphens, never em dashes.
