---
kind: spec
---
# Spec: an agent captures an intent

## Requirements

### R1: The agent starts an intent with `asdlc intent new` and writes only its body

The path, the branch name and the frontmatter are the command's. The agent does not type them.

### R2: The intent states the problem in the requester's own words and facts

A fact in the intent is one the requester gave. Their terms are kept, not swapped for the agent's.

### R3: The intent names no solution the requester did not state

### R4: Each proposed outcome is one a person can judge

A reader can say yes or no to each line without asking what it means.

### R5: What is not known is an open question, not a guess

Something the requester did not say appears as `### Q<n>:`, never as a statement in the text.

### R6: The agent shows the draft and applies corrections before it pushes

### R7: The agent opens a pull request and never merges it

### R8: The intent's branch changes no file but its `intent.md`

### R9: A request that fits in a handful of tool calls produces no intent

The agent does the work and writes no document.

### R10: `asdlc` runs in the shell of an eval run

Today it does not. The run's sandbox cannot read the repository, and it cannot reach the network to fetch the command.

### R11: The `asdlc` a session runs is the one its plugin shipped

An older `asdlc` elsewhere on `PATH` does not win.

### R12: The skill has an eval case where it must act and one where it must stay out

### R13: `just check` fails when a skill lacks either kind of case

It reads files only. It runs no model.

### R14: Every eval case has a grader that is a pattern, not a judge

### R15: One command runs the plugin's eval cases locally

### R16: An intent's branch records when the intent was started

Time to a committed intent can then be read from git alone.

## Design

### The skill

`plugins/asdlc/skills/capturing-intent/SKILL.md`. It works in this order:

1. Decide whether the request needs an intent. If it fits in a handful of tool calls, do the work and stop (R9).
2. Run `asdlc intent new <slug>`. This starts the branch and the clock (R1, R16). It comes before the questions, so the clock starts with the conversation.
3. Ask what an analyst would ask: the scope, who is affected, what must not break, and how success will be judged. Ask only what the request did not already say.
4. Write the body. The problem is in the requester's words (R2) with no solution added (R3). Each outcome can be judged (R4). Constraints are one to a line. What is unknown is a `### Q<n>:` (R5).
5. Show the draft and apply what the requester corrects (R6).
6. Commit, push, open the pull request, and stop (R7, R8).

### The command in a session

A session-start hook installs the package. This is the route the plugin documentation gives for Python dependencies.

- It installs into `${CLAUDE_PLUGIN_DATA}` when the copy there is not the plugin's version. In a checkout it installs from the working tree. An installed plugin fetches the repository at its release's tag.
- It puts a copy in the session's temp folder, and puts that copy first on `PATH` through `CLAUDE_ENV_FILE` (R10, R11). The copy is needed because an eval run's sandbox cannot read the data directory. A probe showed it can read the temp folder, and ran `asdlc version` from there.
- The lint and guard hooks call the installed copy.
- `plugins/asdlc/bin/` and its two-route launcher are removed. The launcher fetched the command on every call when installed.

### The eval cases

Cases live in `plugins/asdlc/evals/<case>/case.yaml`. That is the folder and the format `claude plugin eval` reads, so no runner is written here.

- A case's `tags` name its skill and say `acts` or `stays-out` (R12).
- A test under `tests/` reads the skills and the cases. It fails when a skill lacks either kind, or a case has no pattern grader (R13, R14).
- `just eval` runs `claude plugin eval plugins/asdlc` (R15). It is not part of `just check` and not part of CI.

The two cases:

- `intent-in-their-words` acts. Its prompt gives a problem with facts planted in it and one thing left unsaid. Patterns check that `asdlc intent new` ran, that `intent.md` exists and holds the planted facts, and that nothing was pushed or merged. A judge checks R2, R3 and R4.
- `small-request-no-intent` stays out. Its prompt is a one-line fix. A pattern checks that no file under `intent/` was created.

### The start of an intent

`asdlc intent new` makes the branch's first commit, an empty one, before it writes the file (R16). Time to a committed intent is the gap between that commit and the one that adds `intent.md`. Nothing is written into the document. An intent started by hand is recorded the same way, because the command does it and not the skill.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The agent never merges. Accepting an intent stays a person's decision. | R7. The skill stops once the pull request is open, and the case that acts fails if a merge command ran. |
| The skill writes the prose only. Paths, branch names and frontmatter come from `asdlc intent new`. | R1. |
| The branch changes only `intent.md`, so the guard stays clean. | R8. The start commit is empty, so it changes no file. |
| Evals never block a pull request. | R15. The cases run only when someone runs `just eval`. The check in R13 reads files and runs no model. |
| The layers hold: decisions in `asdlc/domain`, reading in `asdlc/io`, wording in `asdlc/presentation`. | The start commit is the only change inside the package: `io` makes it and `cli` asks for it. The install script is shell because it runs before the package is there, and it decides one thing: whether the installed copy is current. |

## Open questions from intent

### Q1: How much of the eval suite arrives with this intent - the case format and a shape check only, or the runner as well?
- answer: answered

The runner already exists. Claude Code ships `claude plugin eval`, so the cases arrive in its format and run from the start (R12 to R15). We write no runner.

### Q2: Where do eval cases for a skill live, in one `evals/` folder or beside the skill?
- answer: answered

In `plugins/asdlc/evals/`, the one folder `claude plugin eval` reads for a plugin. A case's tags name its skill.

### Q3: Should the skill record when the conversation started, so time to a committed intent can be measured later?
- answer: answered

Yes, in git and not in the document (R16). The course measures the time from the first conversation to a committed `intent.md`, and nothing else records the start. The command records it, not the skill, so an intent started by hand is measured too.

## Areas of concern

### C1: An eval run needs Python 3.15 on the sandboxed shell's `PATH`
- owner: Bruk Habtu

The probe ran the copy with the machine's own Python. uv could not start inside the sandbox. A machine or a CI runner without Python 3.15 on `PATH` cannot run the cases until that is solved.

### C2: An eval run is one turn with no network
- owner: Bruk Habtu

`gh` is signed out in a run and nothing can be pushed. So the case that acts can check the draft, and that nothing was pushed or merged. It cannot check that a correction was applied (R6) or that a pull request was opened (R7). Those two are proved by using the skill on a real intent.

### C3: The course gates configuration changes on eval results, and the intent says evals never block
- owner: Bruk Habtu

Decided: once the cases run in CI, a pull request that changes what they measure must pass them. That is the plugin's skills, agents and hooks, and the cases themselves. A pull request that changes none of those does not run them. This is the course's rule.

This intent does not put the cases in CI, so its constraint still holds here: the cases run by hand. The intent that puts them in CI builds the rule, and settles two things:

- What failing means. A judge's verdict varies between runs (C4), so a drop against the last result on `main` is a fairer test than one red case.
- Whether the cases also run on a schedule. A model update can change how a skill behaves with no pull request at all, and the course runs its cases nightly for that reason.

### C4: The checks a judge makes vary from run to run
- owner: Bruk Habtu

R2, R3 and R4 need a judge, and one run can pass or fail by chance. The cases run three times each, and the pass mark is set once the first runs show the spread.

### C5: An installed plugin needs the network on the first session after an update
- owner: Bruk Habtu

The hook fetches the repository at the release's tag, so a release must tag. Version 2 has no release yet, and until it has one the hook fetches `main`.
