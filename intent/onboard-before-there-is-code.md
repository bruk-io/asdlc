# Intent: a repository can start before it has code

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

The orchestrate loop onboards a repository the first time work needs it, before the first worker is launched: it reads the code for its layers, runs its build, test and lint commands on a clean checkout, and publishes the repository's plugin. A new project has none of that to read. On steg, the first tasks were spikes and the task that creates the workspace, so at the first pick there were no commands that did anything and no layers at all.

The loop has no answer for that. Its choices are to onboard, to wait for an onboarding already open, or to go on because a plugin is published. The orchestrator skipped onboarding, wrote a note on each task saying why, and a task was added by hand to onboard once the workspace exists. A different session could as easily have published a plugin that verified commands doing nothing and described layers it guessed, which every later worker would then be given as fact.

I want starting a project from nothing to be a path the loop knows, not a gap an orchestrator has to improvise across.

## Proposed outcome

- When work is picked in a repository with nothing yet to onboard, the loop has a stated answer: what is done now, what is put off, and where that is recorded.
- Nothing is published that describes commands that were not run or layers that are not in the code.
- The onboarding that was put off is on the board as work, so it happens when there is something to onboard and is not forgotten.
- Workers launched before onboarding are told that the repository has no plugin yet, so they do not look for rules or verified commands that are not there.
- Once the repository has code, the next pick onboards it as the loop does today.

## Affected users and systems

- Anyone starting a new project with asdlc, and the first workers in it.
- The orchestrate and onboard-repo skills, `asdlc-plugin status`, and the worker agent.
- Tasks whose plans were written before the repository had rules.

## Constraints

- Onboarding still never writes down a command it did not run, or a layer the code does not have.
- A repository with code is never treated as empty to skip onboarding.
- Skills are steering paths: a change to them passes the eval gate (spec R23).

## Open questions

- [ ] What tells a repository with nothing to onboard from one that simply has no plugin: no build file, no verified command that does work, or the orchestrator's judgement?
- [ ] Is the put-off onboarding a task the loop creates itself, as a draft for the person to accept, or something `asdlc-plugin status` reports each round until it can be done?
- [ ] Should a first, thin plugin be published at once (the entrypoint commands and nothing else) and extended later, or nothing until there is real content?
- [ ] Which task's completion makes the repository ready: can that be told from the board, or only by looking at the code?
- [ ] Do plans written before onboarding need to be checked again once the rules exist?
