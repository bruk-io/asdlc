# How changes here are reviewed

Every pull request is reviewed by Claude in CI before a person merges it (spec R15). The review never approves or blocks; the person who merges decides. These rules are read from `main`, never from the pull request under review, so a change can't loosen the rules that judge it.

## Passes

Tag every finding with its pass.

- **Bugs.** Logic errors, unhandled edge cases, regressions, and code that won't run on Python 3.15.
- **Security.** Secrets or tokens reachable by untrusted code, workflows that run a pull request's code with credentials, injection through shell commands built from input, and hooks or checks that fail silently instead of saying so.
- **Compliance.** Does the change do what its plan says? A change built from a plan cites it (`plan/<slug>.md`) in its description; compare the files it touches and what it does with the plan's file list and order of work. A change to an artefact (`intent/`, `spec/`, `plan/`) must keep the shape the next stage reads. A departure from the plan is a finding unless the same pull request updates the plan and says why.

## Severity

- **Important**: breaks behaviour, weakens a check or a test, lets the plugin judge itself (spec R21, R23), leaks a credential, or departs from the plan without updating it.
- **Nit**: anything else. Report at most five nits per review, and summarise the rest as a count.

## Skip

- Anything `./scripts/check` or CI already enforces: artefact shape, tests passing, the Python version, the plugin manifests.
- Formatting and wording preferences, unless the wording in a skill would make a model do the wrong thing.
