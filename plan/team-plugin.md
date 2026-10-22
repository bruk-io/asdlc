# Plan: the tasks repository as a marketplace, the team plugin, and rules in every session

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R11 (a skill holds one policy with its owner, source and enforcement), R12 (agents get the same conventions in every worktree), R13 (one verified command per check tier, and evidence from the toolchain), R26 (the new hook logs what it injects and every error)

The tasks repository from the shared-board change holds only the Backlog.md board. Code repositories get no agent setup at all, so the team's conventions have to reach agents some other way. This change makes the tasks repository a Claude Code plugin marketplace: `asdlc init-board` copies in a `team` plugin (the team's testing skill and rules, and the cross-repository contract a lead writes), the tasks repository's settings (`asdlc.toml`) and the developer preferences folder (`devs/`). Developers add the marketplace once. A new asdlc hook, `load_rules`, finds the tasks repository from the code repository an agent touches and injects the team's rules, and that repository's own rules, the first time each one matches in a context. It also defines the per-repository plugin format that the onboarding pull request (PR 4) will generate.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | `init_board` calls one new function that copies `templates/board/` into the board, skipping every file that already exists, and commits what it added | R12 |
| `scripts/repo_slug.py` | yes | `repo_slug(remote)`: a code repository's `owner-repo` slug from its `origin` URL (ssh, scp-like, https, local path); `origin_url(repo)` reads it with git. One module, so `asdlc register` (PR 2a) and the hook derive the same slug | R12 |
| `hooks/load_rules.py` | yes | PostToolUse on `Read|Edit|Write|NotebookEdit`: find the board, pick the team and repository rules whose `paths` match the touched file and that this context hasn't had, inject them capped at 10,000 characters, record them per session and agent. SessionStart (`startup`, `clear`, `compact`) forgets what was delivered | R12, R26 |
| `hooks/hooks.json` | no | Two additive entries: the rule loader on PostToolUse and on SessionStart, same uv wrapper as the guards | R12 |
| `templates/board/.claude-plugin/marketplace.json` | yes | The tasks repository's marketplace, listing the `team` plugin; its name is filled from the board's folder | R12 |
| `templates/board/plugins/team/.claude-plugin/plugin.json` | yes | The team plugin's manifest | R12 |
| `templates/board/plugins/team/README.md` | yes | What the team plugin holds, how rules are scoped and delivered, where an analytics or observability skill or rule goes | R11 |
| `templates/board/plugins/team/skills/testing/SKILL.md` | yes | The team's testing policy: choosing, writing and running tests, verifying with the repository's own checks, recording the evidence on the task | R11, R13 |
| `templates/board/plugins/team/rules/testing.md` | yes | The language-neutral testing rule, scoped to test files in any language | R11, R13 |
| `templates/board/plugins/team/rules/testing-python.md` | yes | Python testing techniques, scoped to Python test files | R13 |
| `templates/board/plugins/team/skills/writing-a-contract/SKILL.md` | yes | How a lead writes and keeps the cross-repository contract for a large feature | R11 |
| `templates/board/plugins/team/templates/contract.md` | yes | The contract: behaviour and states, API, analytics events, traces and logs, which child task implements which part, changes | R11 |
| `templates/board/asdlc.toml` | yes | `stale_after = "2h"` and `review_fallback_after = "30m"`, each commented | - |
| `templates/board/devs/README.md` | yes | The `devs/<name>.yaml` format, a strict flat YAML subset | - |
| `templates/board/devs/example.yaml` | yes | One example preferences file | - |
| `docs/repo-plugins.md` | yes | The per-repository plugin format: `plugin.json`, `layers.toml`, `rules/*.md` with `paths`, `skills/`, `commands.toml` | R12, R13 |
| `tests/test_repo_slug.py` | yes | Slugs from ssh, scp-like, https, `ssh://` with a port, `file://` and local-path remotes; refusals; `slug_of` on a real repository | R12 |
| `tests/test_load_rules.py` | yes | Glob matching, rule and layers parsing, the cap, once per context, the reset, no board, a repository with no plugin yet or no origin, a task worktree, the layer, errors reported once, against real git repositories; the `hooks.json` entries | R12, R26 |
| `tests/test_board_scaffolding.py` | yes | `init-board` on a fresh board and on an existing one (nothing overwritten), the marketplace and team plugin's JSON shape, and `claude plugin validate` on both when it is installed | R12 |
| `README.md` | no | A short "Tasks repository as a marketplace" section: adding the marketplace, how rules reach agents | - |

## Order of work

1. `scripts/repo_slug.py` and `tests/test_repo_slug.py`: the slug is the contract with PR 2a, so it is settled first.
2. The scaffolding templates, then the copy in `init-board` and its tests (fresh board, existing board with an edited file, a second run that adds nothing).
3. Validate the scaffolded marketplace and team plugin with `claude plugin validate` and fix what it reports.
4. The rule loader's logic (frontmatter `paths`, globs, layers, the capped injection, the seen set), then its shell (board lookup, state file, SessionStart reset), then the hook against real repositories.
5. `hooks.json`, `docs/repo-plugins.md`, the README section.
6. `./scripts/check` and the plugin validation.

## Risks

- **The loader runs on every Read.** It starts uv and runs up to three git commands per file touched. Files outside a repository or in one with no board return after the first git call. The warm start through uv is already measured by the guards' tests at well under the timeout; if it proves slow in the pilot, a shell pre-filter comes next.
- **A rule delivered once is lost after compaction.** The loader forgets what the main context had on SessionStart `compact`, `clear` and `startup`, so rules come back on the next touch. A subagent's context is tracked apart from its parent's (`agent_id`), because a rule in the orchestrator's context is not in its worker's.
- **Two hooks in one context at once** (parallel Reads) could both deliver a rule. The state file is locked while it is read and written, and when it can't be written the rule is delivered again rather than never.
- **Slugs that collide.** `owner-repo` drops the host and any group above the owner, so `github.com/a/b` and `gitlab.com/a/b`, or `group/one/b` and `group/two/b`'s owners, could share a slug. Rare in one team; `docs/repo-plugins.md` says so.
- **The board clone is stale.** Rules come from the local clone of the tasks repository, as last pulled. Every `asdlc` board command fetches it, so it is rarely far behind.
- **Overwriting a team's edits.** `init-board` writes only files that don't exist and commits only the paths it wrote, so a second run never changes what the team already has.
- **PR 2a edits `scripts/asdlc` in parallel.** This change touches only `init_board` and adds one function beside it, so the merge is mechanical.

## Departures from the brief

- The seen set is kept per session and per agent (`agent_id`), not per session alone, and the main context's set is forgotten on SessionStart `compact`, `clear` and `startup`. A subagent is a separate context, and compaction drops delivered rules; without both, workers would never get rules the orchestrator had already seen, and nobody would get them back after compaction. This adds a SessionStart entry to `hooks.json`.
- The loader logs each injection and each error to the decision log, not every file it looks at: a Read that delivers nothing decides nothing, and logging it would bury the log.
- The 10,000-character cap is on the whole injection, not on each rule, since that is what reaches the context at once; a rule cut short, or one that didn't fit, says where it is in full.
- `devs/example.yaml` is the one example file; `asdlc` should skip it when it reads preferences (noted for PR 2a). `devs/README.md` gives defaults for the keys a file leaves out (`prefer` and `avoid` empty, `workers` 3, `review` true), which PR 2a's reader should match.
- `{plugin_root}` in a rule's body becomes its plugin's folder in the board clone, so a repository rule can point at a skill beside it on a machine where that repository's plugin isn't installed.
- The marketplace template's name is a `{{marketplace}}` placeholder that `init-board` fills from the board's folder name, since a marketplace needs a name of its own.
- The slug tests are in `tests/test_repo_slug.py`, one test module per script, as the repository's convention has it.

## Proof

- `./scripts/check` passes, including `tests/test_load_rules.py` and `tests/test_board_scaffolding.py`.
- `claude plugin validate` passes on the scaffolded marketplace and on `plugins/team`, run by the scaffolding tests when `claude` is installed, and `claude plugin validate .` on this repository.
- The hook, run by hand on a payload for a Python test file in a code repository pointed at a scaffolded board, prints the team's `testing` and `testing-python` rules once, then nothing for the same session.
