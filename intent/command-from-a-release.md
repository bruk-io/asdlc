# Intent: the asdlc command comes from a release

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

`just setup` links `asdlc` and `asdlc-plugin` on the `PATH` to the scripts in a clone of this repository. The skills, agents and hooks come from the installed plugin, which is a release. So the command a person and their workers run is whatever that clone has checked out at that moment.

That showed on 2026-11-13. A fix to `asdlc register` was made in the clone on a branch while another project (steg) was being set up through the same command, and for a time that project ran on an unmerged branch without anyone choosing that. With workers running in the background, switching the clone's branch would have changed the tool under them mid-task. The guide already names the weaker form of this: the clone and the plugin can be at different releases, and "`asdlc doctor` doesn't compare them yet."

I want to work on asdlc, or have agents work on it, while using asdlc on something else, without the two touching.

## Proposed outcome

- The `asdlc` and `asdlc-plugin` a person runs are the ones that belong to the plugin release they have installed, and stay so whatever is checked out in any clone of this repository.
- The scripts, skills, agents and hooks in use are always the same release, and `asdlc doctor` fails, saying how to fix it, if they are not.
- Someone changing asdlc can run the version they are working on deliberately, by a name or a path that is clearly not the installed one.
- Updating the plugin updates the command with it, in one step.
- A machine set up the old way is told what to change, and nothing breaks before it does.

## Affected users and systems

- Anyone who both uses asdlc and changes it, and any agents working on asdlc while it is in use.
- `just setup`, the guide's install steps, `asdlc doctor`, and the skills' fallback (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/asdlc"`).
- `asdlc permissions`, whose allow rules name the command by name and by the clone's path.

## Constraints

- The released version must not edit itself (spec R21), and working on the plugin never means loading it from the working copy.
- Background workers still run the command without a permission prompt.
- A person can still run `asdlc` in their own terminal, since accepting, approving and marking Done are theirs.

## Open questions

- [ ] Where does the command live: a link to the installed plugin's folder, a small launcher that finds the installed release, or a tool installed with uv from a tag?
- [ ] The installed plugin's folder changes with each release. What keeps a link or an allow rule pointing at the current one?
- [ ] What should the development copy be called, so it is never mistaken for the installed one in a command an agent writes?
- [ ] Do the eval suite and the tests, which run the scripts from the working copy by design, need anything to change?
- [ ] Is a mismatch between the command and the plugin a failure in `asdlc doctor`, or should the command itself refuse to run?
