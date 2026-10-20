# asdlc

A Claude Code plugin implementing Anthropic's AI-native SDLC playbook. It builds itself: every change to this repository goes through the plugin's own loop.

## Commands

- `./scripts/check` - every artefact check and every test, under Python 3.15 through uv. Exits non-zero on any failure. Run it before saying any change is done, and paste its result.
- `uv run --script scripts/artefacts.py .` - the artefact checks alone.
- To try the plugin on this repository, load it from a separate worktree of a released commit (`claude --plugin-dir <that worktree>`), never from this working copy: Claude Code refuses edits inside a loaded plugin's own folder, and the released version must not edit itself (spec R21).
- `claude plugin validate .` - the plugin and marketplace manifests. Not `--strict`: it warns that this `CLAUDE.md` doesn't ship with the plugin, which is intended, since it is this repository's own.

## The loop

Nothing changes here except through it. Each stage is a file in git and a pull request; the merge is the gate.

- Intent: `intent/<slug>.md` - the problem, in the requester's words. Merging accepts it.
- Spec: `spec/<slug>.md` - numbered requirements, design, areas of concern; settles every intent question by number. Merging approves it.
- Plan: `plan/<slug>.md` - files, order, risks, proof, citing requirement numbers. Merging approves it; implementation starts after.
- Change: the change itself, in its own pull request, built from the plan.

If a change departs from its plan, update the plan in the same commit and say why.

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
