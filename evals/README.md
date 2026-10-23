# The eval suite

Evals run real Claude Code agents, headless, against throwaway fixtures, and grade what they did with deterministic checks the agent never sees. They check behaviour unit tests can't: whether a worker stops when its claim is gone, whether an orchestrator waits for approval, whether a reviewer names a seeded defect. `scripts/eval` runs them; [the guide](../docs/guide.md#running-evals) says how to run them, and this page says how to write one.

This folder is a protected path (spec R23): a pull request that changes the plugin can't change anything here, and CI enforces it. New cases arrive in pull requests of their own.

## A case

Each case is a folder under `cases/`:

- `case.toml`: what the case is and how it runs.
- `case.py`: the fixture builder, the reference run, the case's own checks, and anything it collects after the run.

```toml
source = "Where the case comes from: the review finding or incident it guards, or the person who asked for it (R24)."
kind = "outcome"        # outcome: the end state is graded. process: the order is the point.
suite = "regression"    # regression: should hold near 100%. capability: measures how well.
description = "What happens, and what passing looks like, in a few sentences."
checks = ["setting_changed", "no_intent_captured"]
arms = ["with-plugin"]  # leave out to run under both arms; say with-plugin when the case needs the plugin's agents

[run]
model = "sonnet"        # the session's model; --model overrides it, and workers follow asdlc route
effort = "medium"
agent = ""              # a plugin agent to run as the session, such as asdlc:worker or asdlc:reviewer
max_turns = 60
max_budget_usd = 5.0
timeout_minutes = 30
permission_mode = "acceptEdits"

[[sessions]]
prompt = "What the person types, with {facts} from the fixture."

[[sessions]]
before = ["approve_waiting_plans"]   # person steps, run between the two sessions
prompt = "I've approved them:\n\n{person}\n\nCarry on."
```

A case has `sessions` (the first is fresh, each later one resumes it after its person steps) or `items` (a trigger set: each item's prompt runs in a fresh session, with an `expect`ed skill or `none`).

`case.py` defines:

- `build(fixture) -> facts`: builds the world in the trial's temporary folder and returns what the prompts and checks need. `fixtures.team(...)` makes the usual one: a tasks repository with its board, acme/api (a few lines of Python with tests, its repository plugin published), and a machine for each engineer. Everything under `fixture.agent` is what the agent may see; other engineers' machines go under `fixture.others`.
- `reference(script, fixture, facts, session) -> final message`: the correct actions, scripted with no model. Each `script.bash`, `script.write`, `script.read`, `script.skill` and `script.agent` really runs and is written down as a session would write it, so the checks read the same thing from a reference run as from a real one.
- `null(...)`, optional: what the null run does. By default it does nothing.
- `collect(fixture, facts) -> dict`, optional: anything else the checks need, gathered on the host after the agent stopped (a file's text, the result of running the pushed code).
- Checks, by the names `case.toml` gives: `def name(outcome, case) -> (passed, why)`. A name is looked up in `case.py`, then in `checks.py`, which holds the checks several cases share.

Person steps live in `steps.py` (or in the case's own `case.py`): `def name(fixture, facts) -> what the person did`. Each runs as the agent's engineer, on the host, and the trace records it with the board as it stood.

## The bar a case must clear

**Two experts.** Two people who know the plugin would agree, reading the transcript, on whether the trial passed. If they could argue about it, the check is measuring the wrong thing or the case is ambiguous: tighten the prompt or the check until they wouldn't.

**A reference run that passes and a null run that fails.** `scripts/eval validate` builds each case's fixture twice, runs the reference in one and the null run in the other, and fails unless the reference passes every check and the null run fails at least one. A check the reference can't pass is wrong; a set of checks doing nothing passes is too weak to mean anything. `./scripts/check` runs `validate`, and it makes no model calls.

**Graded on the outcome, outside the agent's reach.** Checks read only the outcome, copied out after the agent stopped: the board's history on its origin, the agent's board clone, the code origins (branches, commits, and every update their reflogs saw, so a forced push is caught), the hook decision logs, the stand-in `gh`'s calls, and the transcript's events. The agent's environment holds only its fixture and prompt; this folder, the checks and the reference runs are never where it can read them.

**Outcome or process, deliberately.** Grade the end state unless the order is the point. A process case (approval before building, say) uses ordered trace assertions: `person_index`, `board_commits_before`, `runs_command` and `edits_under` in `scripts/eval` place an event before or after a person's step. Don't grade the path an agent took to a correct end state; agents find routes nobody scripted.

**From an incident or a person (R24).** `source` names the review finding, the incident or the person behind the case.

## Kinds and suites

| | Outcome | Process |
|---|---|---|
| Regression | A fixed bug stays fixed: the reaped worker stops, the sent-back branch survives | The approval gate holds in order |
| Capability | How well a judgement is made: reviewer recall and false alarms, skill triggering | Rare; prefer outcome |

Regression cases should pass near 100% of the time; a drop is a bug. Capability cases measure a rate, and only the trend between versions means anything.

## What a run records

Every trial keeps its transcripts (stream-json, one file per session, with subagent transcripts beside them), `outcome.json`, and `trial.json` with each check's verdict and the counts: tokens by model (input, output, cache reads, cache writes and how many of those were to the one-hour cache), turns, tool calls, tool errors, permission denials, time, the model, the arm and the plugin's commit. Cost is derived when the report is made, from `prices.toml`, so a run can be repriced and runs on a subscription are priced like any other (R29).
