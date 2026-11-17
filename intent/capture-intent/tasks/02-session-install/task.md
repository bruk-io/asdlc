---
kind: task
step: 2
delivers: [R11, R12]
size: 3
---
# Task: a session installs asdlc when it starts

## What to build

Step 2 of the plan. A `SessionStart` hook runs `plugins/asdlc/scripts/install`, a shell script that:

1. Chooses the source: the working tree in a checkout, otherwise the repository on GitHub at the one ref the script names.
2. Installs into `${CLAUDE_PLUGIN_DATA}/asdlc/venv`, a relocatable environment on uv's own Python 3.15. A checkout installs every time. An installed plugin installs only when the stamp beside the environment is not `plugin.json`'s version.
3. Copies the environment to a folder under `$TMPDIR` named for the session, and puts its `bin` first on `PATH` through `$CLAUDE_ENV_FILE`.

It works under a lock. The lint and guard hooks call the installed copy and say why when it is missing. `plugins/asdlc/bin/asdlc` is deleted, and `CLAUDE.md` and `README.md` describe the install in its place.

A draft that passed two probes under `claude plugin eval` is described in the plan's Risks.

## Done when

- `tests/test_install.py` passes: after the script runs from this checkout, a shell with an older `asdlc` earlier on `PATH` runs the package's version once it reads the env file.
- The same file shows the script's one decision with a stand-in `uv`: a current stamp asks for no install, and any other stamp asks for one, from the GitHub ref.
- `hooks.json` has the `SessionStart` entry, and its lint and guard commands no longer start uv.
- `plugins/asdlc/bin/` is gone and no document mentions it.
- `just check` passes, and `claude plugin validate plugins/asdlc` passes.
