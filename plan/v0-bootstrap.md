# Plan: version 0, the hand-built bootstrap

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R1 (intent, spec and plan only), R2, R3 (by hand only), R7, R9, R10, R11, R13, R23, R26

Version 0 is the playbook's no-prerequisite plays, built by hand: capture intent, plan mode, CLAUDE.md, skills, the feedback loop and build-time hooks. Every later version is built by the plugin itself (R20). Version 0 has no eval suite yet, so it and the changes immediately after it merge on review alone until the gate in R22 exists.

## Language

Scripts and hooks are Python 3.15 (released 2026-10-09), standard library only, run through uv. Each script declares `requires-python = ">=3.15"` in an inline metadata block (PEP 723) and runs as `uv run --script <file>`, so uv fetches 3.15 the first time and nothing else needs installing. uv is the one prerequisite, named in the README.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `.claude-plugin/plugin.json` | yes | Plugin manifest | - |
| `.claude-plugin/marketplace.json` | yes | A marketplace with this plugin, so it installs from the repository | - |
| `CLAUDE.md` | yes | This repository's own: commands, layout, the loop, under a page | R10 |
| `templates/intent.md` | yes | Problem, proposed outcome, affected users and systems, constraints, open questions | R7 |
| `templates/spec.md` | yes | Numbered requirements, design, areas of concern, open questions settled, out of scope | R8 |
| `templates/plan.md` | yes | Files that change, order of work, risks, proof, requirements delivered | R9 |
| `templates/policy-skill.md` | yes | A policy skill: owner, source, the policy, and the hook or check that enforces it if it must always hold | R11 |
| `skills/capture-intent/SKILL.md` | yes | Analyst questions, the requester's words, the draft intent, a pull request as the gate | R7 |
| `skills/plan-change/SKILL.md` | yes | Read intent and spec, write the plan, challenge it until it stands alone, a pull request as the gate | R9 |
| `skills/write-policy-skill/SKILL.md` | yes | Turn one policy into a skill from the template, and name its enforcement | R11 |
| `commands/intent.md` | yes | Runs capture-intent by hand | R3 |
| `commands/plan.md` | yes | Runs plan-change by hand | R3 |
| `hooks/hooks.json` | yes | Registers the hooks below, each run with `uv run --script` | R13, R26 |
| `hooks/decision_log.py` | yes | Appends one JSON line per hook decision to `.asdlc/hooks.jsonl` | R26 |
| `hooks/guard_test_edits.py` | yes | On a `fix/` branch, denies edits to test files that exist on the merge base, with the reason | R13 |
| `scripts/check` | yes | The single check command: every artefact check, then the tests under 3.15 through uv; exits non-zero on any failure | R13 |
| `scripts/artefacts.py` | yes | Shape checks for intent, spec and plan files; open questions settled; CLAUDE.md under a page | R1, R7, R8, R9, R10 |
| `scripts/protected_paths.py` | yes | Fails a pull request that changes the plugin and anything under `evals/` together | R23 |
| `tests/` | yes | One `unittest` module per script and hook, using throwaway git repositories | R13 |
| `.github/workflows/ci.yml` | yes | Installs uv, then runs `scripts/check` and `scripts/protected_paths.py` on every pull request | R13, R23 |
| `.gitignore` | yes | Ignores `.asdlc/` | R26 |
| `README.md` | no | Install (uv is the prerequisite), what version 0 does, and what it does not do yet | - |

## Order of work

1. `scripts/check` and the `unittest` layout under 3.15 through uv, with one passing test, so every later step has a feedback loop.
2. The templates, then `scripts/artefacts.py` with tests. Run it over this repository's existing intent, spec and this plan; all three must pass before going on.
3. `hooks/decision_log.py`, then `hooks/guard_test_edits.py` built on it, with tests that run each hook as a subprocess against a throwaway repository.
4. `hooks/hooks.json`, the manifest and the marketplace entry. Validate with `claude plugin validate`.
5. The three skills and two commands.
6. `CLAUDE.md`, `.gitignore`, and the README update.
7. `scripts/protected_paths.py` with tests, then CI.
8. Install the plugin from this repository in a fresh session and run `/asdlc:intent` on a small real need; the resulting draft must pass `scripts/artefacts.py`.

## Risks

- **Version 0 judges itself.** Until the eval gate exists, nothing but review stands behind the skills. Mitigation: keep version 0 small, and make building the gate the next intent.
- **The test-edit guard keys on a branch name.** A fix done on a branch not named `fix/` is unguarded. Accepted for version 0; the plan template's bug kind replaces the branch name later.
- **The decision log is per machine.** `.asdlc/hooks.jsonl` is gitignored, so cloud sessions and other machines keep separate logs. Collecting them is part of the session-index change (R27).
- **uv on the hook path.** Every hook starts through uv, so a machine without uv runs no guards, and the first run waits for uv to fetch 3.15. Mitigation: each hook command fails loudly with an install message when uv is missing, and step 3's tests time a warm hook start; if it is slow enough to notice, the hooks move to one long-lived entry point.
- **Plugin manifest and hook formats change across Claude Code releases.** `claude plugin validate` in step 4 and in CI catches a broken manifest before release.
- **Skills that over-trigger.** Capture-intent must not fire on small requests. Without evals, this is checked by hand in step 8, and becomes a should-stay-quiet eval later.

## Proof

- `scripts/check` exits 0 locally and in CI.
- `scripts/artefacts.py` passes on this repository's intent, spec and this plan, and fails on a test fixture missing each required section.
- `guard_test_edits.py` denies an edit to an existing test file on a `fix/` branch, allows a new test file there, and allows any edit on another branch; every decision appears in `.asdlc/hooks.jsonl`.
- `scripts/protected_paths.py` fails a fixture pull request touching `skills/` and `evals/` together, and passes one touching either alone.
- `claude plugin validate` passes.
- Step 8's draft intent passes the intent check.

## After this change

Each becomes its own intent, in this order: trace checks and the session index (R27), one task eval end to end, the requirements-and-design play (R8), the eval gate (R22), then the remaining plays in dependency order.
