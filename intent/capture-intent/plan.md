---
kind: plan
---
# Plan: a skill that captures an intent

## Files that change

- src/asdlc/io/git.py
- src/asdlc/cli.py
- tests/io/test_git.py
- tests/test_cli.py
- plugins/asdlc/scripts/install (new)
- plugins/asdlc/hooks/hooks.json
- plugins/asdlc/bin/asdlc (removed)
- tests/test_install.py (new)
- tests/test_evals.py (new)
- pyproject.toml
- uv.lock
- plugins/asdlc/skills/capturing-intent/SKILL.md (new)
- plugins/asdlc/evals/intent-in-their-words/case.yaml (new)
- plugins/asdlc/evals/intent-in-their-words/scaffold.sh (new)
- plugins/asdlc/evals/small-request-no-intent/case.yaml (new)
- plugins/asdlc/evals/small-request-no-intent/scaffold.sh (new)
- justfile
- .gitignore
- CLAUDE.md
- README.md

## Order of work

Steps 1, 2 and 3 do not depend on each other. Step 4 needs 2 and 3.

### Step 1: `asdlc intent new` records the start of an intent
- delivers: R17

- `src/asdlc/io/git.py` gains a function that makes an empty commit and says whether git accepted it.
- `intent new` in `src/asdlc/cli.py` calls it when the intent's branch has no commit of its own, before it writes the file. The subject is `Start intent <slug>`.
- When git refuses, as it does when it cannot tell who is committing, the command says so, exits 1 and writes no file.

`spec new`, `plan new` and `task new` do not change. Only an intent's start is measured.

### Step 2: A session installs `asdlc` when it starts
- delivers: R11, R12

`plugins/asdlc/scripts/install` is a shell script. A new `SessionStart` entry in `hooks.json` runs it. It does three things in order, under a lock so two sessions starting together cannot copy a half-written folder.

1. **Choose the source.** In a checkout, the working tree: the repository's root is two folders above the plugin and holds `pyproject.toml` and `src/asdlc`. Otherwise the repository on GitHub at one ref, named on one line of the script. That ref is `main` until version 2 has a release (C5).
2. **Install into `${CLAUDE_PLUGIN_DATA}/asdlc/venv`.** It is a relocatable virtual environment on uv's own Python 3.15: `uv venv --relocatable --managed-python`, then `uv pip install`. A checkout installs every time, because the working tree changes without the version changing. That and the copy take 0.6 seconds here. An installed plugin installs only when a stamp file beside the environment does not hold `plugin.json`'s version. This is the one decision the script makes.
3. **Copy it for the session.** `cp -R` to a folder under `$TMPDIR` named for the session id in the hook's input, then one line appended to `$CLAUDE_ENV_FILE` that puts the copy's `bin` first on `PATH`.

The rest of the step:

- The lint and guard commands in `hooks.json` call `${CLAUDE_PLUGIN_DATA}/asdlc/venv/bin/asdlc` directly. When that file is missing, each says that `asdlc` was not installed for this session and so the check did not run. Their two clauses about uv go, because a hook call no longer starts uv.
- When uv is missing or the install fails, the script says why on stderr and exits 1.
- `plugins/asdlc/bin/asdlc` is deleted. `CLAUDE.md` and `README.md` lose their lines about it and describe the install.
- `tests/test_install.py` runs the script against temporary folders. See Proof.

### Step 3: `just check` judges the shape of the eval cases
- delivers: R14, R15

`tests/test_evals.py` reads the folder names under `plugins/asdlc/skills/` and every `plugins/asdlc/evals/*/case.yaml`. It fails, naming the skill or the case, when:

- a skill has no case tagged with its name and `acts`, or none tagged with its name and `stays-out` (R14);
- a case has no grader of type `regex` or `file_exists` (R15).

The two rules are one function that takes the skills' names and the parsed cases and returns what is wrong. It has tests of its own on made-up cases, so each rule is seen to fail before any skill exists. It lives in the test module and not in the package, as the spec's design has it.

Reading YAML needs `pyyaml`. It goes in the `dev` group in `pyproject.toml`. click stays the only runtime dependency.

### Step 4: The skill, its two cases, and `just eval`
- delivers: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R13, R15, R16

The skill and its cases land in one pull request. After step 3, `just check` fails on a skill without both kinds of case.

**The skill.** `plugins/asdlc/skills/capturing-intent/SKILL.md`. Its description says when it loads: someone describes a problem to solve, or asks for work larger than a handful of tool calls (R1). Its body is the six steps of the spec's design, in that order (R2 to R10).

**The cases.** Each is a folder under `plugins/asdlc/evals/` holding `case.yaml` and `scaffold.sh`. The scaffold script makes the run's folder a git repository with a `main`, one commit and a `user.name`. `asdlc intent new` needs all three.

- `intent-in-their-words`, tagged `capturing-intent` and `acts`. A run is one turn (C2), so the prompt already says the four things the skill asks about: the scope, who is affected, what must not break, and how success is judged. The skill then has nothing to ask and reaches the draft. The prompt plants two facts, and names one thing the requester says they do not know. Patterns check that:
  - the skill loaded (R1);
  - `asdlc intent new` ran, and the only file created is `intent/<slug>/intent.md` (R2, R9);
  - the draft holds both planted facts (R3) and a `### Q1:` (R6);
  - no `git push` and no `gh pr` command ran (R7, R8).

  A judge answers one question each for R3, R4 and R5.
- `small-request-no-intent`, tagged `capturing-intent` and `stays-out`. The prompt is a one-line fix to a file the scaffold script wrote. Patterns check that the fix was made and that nothing under `intent/` was created (R10).

**`just eval`** runs `claude plugin eval plugins/asdlc` with `--scaffold`, `--no-publish`, and `--allow-tools` for Bash, Write and Edit (R16). Results land in `plugins/asdlc/evals/results/`, which `.gitignore` gains. It is not part of `just check` or of CI.

`CLAUDE.md` and `README.md` gain the skill, the cases and `just eval`, and `CLAUDE.md` stops saying evals are not built.

## Risks

Step 2 is the riskiest. Everything Claude does through the plugin goes through that install, and when it fails the lint and the guard stop judging. Two probes of a draft of the script, run with `claude plugin eval` on this machine, showed that the route works:

- The session's copy came first on `PATH`, ahead of the version 1 launcher in `~/.local/bin`.
- Inside the run's sandbox, `asdlc version`, `asdlc intent new`, an empty commit, `asdlc document check` and `asdlc branch check` all ran, in a repository a scaffold script made.
- The whole run took 23 seconds, with the install in it.

What the probes also showed, and what is not solved:

- **C1 changes shape.** An environment built on the machine's own Python would not start in the sandbox: `Operation not permitted`. One built on uv's own Python did, because the hook runs with the run's own home folder, uv downloads Python into it, and the sandbox can read it. So an eval run needs no Python on `PATH`, and needs the network at session start instead. It is tried on macOS only.
- **A checkout's copy goes stale during a session.** The hooks run what was installed when the session started. After editing `src/asdlc`, `uv run asdlc` runs the working tree, and a new session refreshes the hooks.
- **Two checkouts share one data folder.** Sessions started with `--plugin-dir` from two worktrees install into the same place, so the first session's hooks run the second's copy. Each session's own `PATH` copy stays right. This matters when workers build asdlc itself in worktrees, and is not solved here.
- **Every session start pays for the install.** 0.6 seconds in a checkout. The first one on a machine also downloads Python.
- **The acting case can fail with a correct skill.** If Claude asks a question before drafting, the one turn ends with no draft. The prompt is written to leave nothing to ask. Scores also vary between runs (C4), so each case runs three times, and this plan sets no pass mark.
- **`intent new` now needs git to know who is committing.** Where git has no name or email to use, the command refuses, where before it wrote the file.

## Proof

`just check` passes on every step's pull request, and CI validates the plugin's manifest.

- **R17.** A test in `tests/test_cli.py`: after `intent new` in a new repository, the branch is one commit ahead of `main`, that commit changes no file, and `asdlc branch check` is clean once `intent.md` is committed. A second test: when git cannot tell who is committing, the command exits 1 and writes no file.
- **R12, and the script's one decision.** `tests/test_install.py`:
  - It runs the script from this checkout into temporary folders. Then, in a shell whose `PATH` starts with a fake `asdlc` that prints `old`, it reads the env file and expects `asdlc version` to print the package's version.
  - It runs the script from a copy of the plugin folder alone, with a stand-in `uv` that records how it was called. A stamp equal to `plugin.json`'s version means no install is asked for. Any other stamp means one install, from the GitHub ref.
- **R11.** The acting case's patterns. `intent/<slug>/intent.md` with its frontmatter can only exist in a run if `asdlc` ran in that run's shell.
- **R14, R15.** `tests/test_evals.py`, on made-up cases and on the real folders.
- **R1 to R6, R9, R10, R13, R16.** `just eval`, three runs a case, with its report pasted into step 4's pull request. A person runs it the first time, because the command asks whether the plugin folder is trusted.
- **R7 and R8.** A run cannot show a correction being applied or a pull request being opened (C2). They are proved by capturing this repository's next intent with the skill in a live session: the draft is shown, one correction is applied, the pull request is opened and not merged, and the guard is clean on its branch.
