# Plan: the asdlc command comes from the installed plugin

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: approved by the owner in session, 2026-11-15, choosing to keep `version` and bump it per release ("Would prefer the latter").
- Delivers: R21 (the released version never edits, or runs from, the copy being worked on), R12 (parallel workers keep one tool under them for the whole task), R20 (the change starts as an intent)

This serves [`intent/command-from-a-release.md`](../intent/command-from-a-release.md), accepted in pull request 50. The intent has no spec of its own, so this plan cites the plugin's spec for its requirement numbers and answers the intent's open questions below.

`asdlc` and `asdlc-plugin` on a person's `PATH` are links into a clone of this repository, so they run whatever that clone has checked out, while the skills, agents and hooks come from the installed plugin. This change makes both commands come from the installed plugin, and makes updates reach an installed plugin at all.

## What was found before planning

- **The installed plugin has not updated since 2026-10-29.** `plugin.json` sets `"version": "0.1.0"`, and Claude Code keeps every install on a set version until the string changes. This machine's install is commit `2ac9e69`, 54 commits behind `main`, while its `asdlc` command is `main`. So steg runs October's skills, agents and hooks with November's scripts today.
- **A plugin's `bin/` folder is on the Bash tool's `PATH` while the plugin is enabled** (Claude Code's plugin reference, Standard layout). Tested on Claude Code 2.1.325 with a throwaway plugin: the command ran by bare name from the plugin's own folder.
- **That folder is added at the end of `PATH`.** In the test it was entry 36, after `~/.local/bin` at entry 11. So anything named `asdlc` in `~/.local/bin` wins over the plugin's own, and `bin/` alone fixes nothing while the old link is there.
- **`CLAUDE_PLUGIN_ROOT` is not set for commands the Bash tool runs**, so a command cannot ask the environment which plugin it belongs to. The `PATH` entry is the only trace of which release a session loaded.
- **A person's own terminal has no plugin `PATH` at all**, and accepting, approving and marking Done are run there.

## The intent's open questions, answered

| Question | Answer |
|---|---|
| Where does the command live? | In the plugin, as `bin/asdlc` and `bin/asdlc-plugin`, which run the scripts beside them. A person's terminal gets a small launcher in `~/.local/bin` that finds the installed plugin and runs its script. It is a copied file, not a link, and holds no asdlc logic |
| What keeps it pointing at the current release? | The launcher looks each time it runs. Inside a Claude session it uses the asdlc plugin `bin/` entry on `PATH`, which is the release that session loaded. Outside one it reads `~/.claude/plugins/installed_plugins.json` and takes the install for the folder it is in, then a user-wide install, then the newest. The allow rules name the installed path with the version as a wildcard |
| What is the development copy called? | It has no name. It is run by path, `./scripts/asdlc`, or by loading a worktree with `claude --plugin-dir`, whose `bin/` the launcher then follows. `asdlc --version` and the `release` line of `asdlc doctor` say which copy is running and where it is |
| Do the eval suite and tests change? | No. They run the scripts by path from the working copy and keep doing so. The launcher and `bin/` wrappers get tests of their own |
| Is a mismatch a doctor failure or a refusal to run? | A `doctor` failure that names the fix. The command does not refuse: with the launcher the mismatch cannot arise by accident, and a refusal would break a machine set up the old way before it has been told what to change |

## How a release is named

Decided by the owner in session, 2026-11-15: `plugin.json` keeps `version`, and a release is a deliberate bump of it. The alternative was to remove the field so that every merge to `main` is a release named by its commit; the owner preferred a numbered release.

A bump that is forgotten leaves every install where it was, silently, which is what happened for the last 54 commits. So the bump gets one command, `just release <version>`, which sets the version and moves the changelog's Unreleased entries under it, and this change is itself released as 0.2.0. The tag (`v<version>`) is made by the person after the merge.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `bin/asdlc`, `bin/asdlc-plugin` | yes | Two-line shell wrappers that run `scripts/asdlc` and `scripts/asdlc-plugin` from the same plugin folder | R21 |
| `scripts/asdlc_launcher.py` | yes | The launcher. Pure logic takes the `PATH` entries, the install records and the current folder and returns the plugin folder to run or the reason there is none; a thin shell reads the files and runs the script in the same process. Standard library only | R21, R12 |
| `scripts/asdlc` | no | `install-command` copies the launcher to `~/.local/bin/asdlc` and `asdlc-plugin`, says what it replaced, and leaves a file it does not recognise alone. `--version` prints the version, the commit when the install record has one, and the folder it runs from. `doctor` passes when the command on `PATH` resolves to the installed plugin, fails with the fix when it is a link into a clone or a different release than the plugin, and warns when run from a working copy. `permissions` names the installed path with a wildcard version and no longer names a clone | R21 |
| `.claude-plugin/plugin.json` | no | `version` becomes `0.2.0`, so installed plugins take this change | R21 |
| `scripts/release.py` | yes | Sets the version in `plugin.json` and moves the changelog's Unreleased entries under a heading for it. Refuses a version that is not newer, and an empty Unreleased section. Logic takes the two files' text and returns the new text | R21 |
| `tests/test_release.py` | yes | The bump, the changelog move and both refusals | R21 |
| `justfile` | no | `release <version>` calls `scripts/release.py`. `setup` stops linking to this clone: it installs the launcher, and tells a machine with the old links what they are and that `asdlc install-command` replaces them. Nothing is removed without that command being run | R21 |
| `tests/test_asdlc_launcher.py` | yes | The resolution order, each refusal's wording, and a run through the launcher that reaches the right script | R21 |
| `tests/test_demo_pilot.py`, `tests/test_guard_board.py` | no | The pilot demonstration's two machines have asdlc as a ready machine now does: the plugin's files installed in a cache folder with no git folder, and the launcher on `PATH`. `permissions` and `doctor` run from that copy. `test_guard_board.py` loads the launcher module the script now imports | R21 |
| `tests/test_asdlc.py`, `tests/test_justfile.py` | no | `install-command`, `--version`, the three `doctor` outcomes, the new allow rules, and `setup` no longer linking to the clone | R21 |
| `docs/guide.md`, `README.md` | no | Install no longer needs a clone: install the plugin, then `! asdlc install-command` in a session. Updating is one step. The "doctor doesn't compare them yet" note goes | - |
| `CHANGELOG.md` | no | One entry | - |

No file under `skills/`, `agents/`, `hooks/` or `commands/` changes. Their fallback line (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/asdlc"`) stays true.

## Order of work

1. This plan, committed before the code.
2. `scripts/asdlc_launcher.py` with its tests, failing first.
3. `bin/` wrappers, and a test that each reaches its script.
4. `asdlc --version`, `install-command` and the `doctor` findings, tests first.
5. The allow rules in `permissions`.
6. `scripts/release.py` and `just release`, tests first, then `just setup`.
7. `just release 0.2.0`.
8. The guide, the README and the changelog.
9. `./scripts/check`.
10. On this machine, after merge: `git tag v0.2.0`, `claude plugin update asdlc@asdlc`, `asdlc install-command`, `asdlc permissions --write`, then the proof below in steg.

## Departures

- **The pilot demonstration changed**, which the first version of this plan did not list. Its machines ran asdlc from this working copy through a hand-written wrapper, which `doctor` now rightly warns about twice, so its "ready machine has no warnings" assertion failed. The machines were made ready by the new standard; no assertion was loosened, and three were added.
- **The launcher and its tests were written together**, not test-first as step 2 said. The later steps were test-first.
- **The `release` line sits beside the command lines in `doctor`**, not first, so the order a person fixes things in is unchanged.

## Risks

- **The launcher itself is outside any release.** It is a copied file that a later release cannot update by itself. It is kept to finding a folder and running a script, `doctor` compares the installed copy with the plugin's and says to run `install-command` when they differ.
- **A session that has not reloaded after an update.** Its skills are the old release. Inside the session the launcher follows that session's `bin/` entry, so its commands stay on the old release too, and Claude Code keeps the old folder for 14 days. The person's terminal moves to the new release at once. Both are the intended behaviour, and `asdlc --version` shows which is which.
- **Whether a background worker's Bash tool gets the plugin's `bin/` entry is untested.** The one test was a foreground `-p` session. If a worker has no such entry the launcher falls back to the install record for the worktree's folder, which is the same release unless an update landed mid-task. Step 10 checks it in a real worker.
- **Installs differ by folder.** steg and one of its worktrees each have their own install record. They point at the same folder today. The launcher picks the record for the folder it is in, so two projects on different releases each get their own.
- **`install-command` writes into `~/.local/bin` and an agent can run it.** It only ever writes the launcher that ships with the release it is run from, so the worst case is the launcher a person would have installed anyway. It passes no gate, so the board guard is left alone and no steering path changes.
- **claude.ai and Cowork refuse a plugin that has a `bin/` folder.** asdlc is installed from its own marketplace in Claude Code and not synced through claude.ai, so nothing is lost today. It rules that route out later.
- **Allow rules with the version as a wildcard.** A wildcard in the middle of a rule is already relied on for `git -C <worktrees>/* ...`. A test asserts the rule text; step 10 checks a worker runs without a prompt.
- **A release that is merged but never bumped.** Still possible: nothing forces `just release`. The changelog's Unreleased section is where it shows, and `asdlc --version` prints the version a machine is on.
- **The cache folder moves from `0.1.0` to `0.2.0`.** Sessions already running keep the old folder until they reload.

## Proof

- `./scripts/check` passes, and its result is in the commit message.
- `asdlc --version` in a terminal prints `0.2.0` and a path under `~/.claude/plugins/cache/`, with this clone on any branch.
- With this clone switched to another branch, `asdlc --version` in steg prints the same version and path as before.
- `./scripts/asdlc --version` prints the working copy's path and says it is not the installed release.
- `asdlc doctor` fails, naming `asdlc install-command`, on a machine whose `asdlc` is still a link into a clone, and passes after that command is run.
- In steg, a background worker runs `asdlc --version` without a prompt and reports the installed version.
