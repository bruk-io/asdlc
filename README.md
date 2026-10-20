# asdlc

An agentic SDLC as a Claude Code plugin, built on Anthropic's AI-native SDLC playbook. It builds itself: every change starts as an intent in `intent/` and runs through the plugin's own loop.

## Install

uv is the one prerequisite: the plugin's hooks and checks are Python 3.15 scripts run through it, and uv fetches 3.15 on first use. Install it from <https://docs.astral.sh/uv/>.

Then, in Claude Code:

```
/plugin install asdlc --marketplace bruk-io/asdlc
```

## What version 0 does

| Play | What you get |
|---|---|
| Capture intent | `/asdlc:intent` and the `capture-intent` skill: an interview, an intent in the requester's words, a pull request whose merge accepts it |
| Plan mode | `/asdlc:plan` and the `plan-change` skill: files, order, risks and proof, citing the spec's requirements, approved by merge |
| Skills | The `write-policy-skill` skill and a template that names each policy's owner, source and enforcement |
| Feedback loop | One check command per repository, and a hook that stops a bug fix on a `fix/` branch from editing an existing test |
| Hooks | Every hook decision logged to `.asdlc/hooks.jsonl` |
| CLAUDE.md | A check that keeps it under 60 lines |

Templates for intents, specs and plans are in `templates/`, and `scripts/artefacts.py` checks that each artefact has what the next stage needs.

## What it does not do yet

- No eval suite, so changes merge on review alone until the eval gate lands.
- The requirements-and-design play, PR review, approval gates, CI/CD and closing the loop on metrics are specified in `spec/agentic-sdlc-plugin.md` and come in later versions.

## How it is built

- [The intent](intent/agentic-sdlc-plugin.md)
- [The spec](spec/agentic-sdlc-plugin.md) and [its evals](spec/agentic-sdlc-plugin-evals.md)
- [The plan for version 0](plan/v0-bootstrap.md)
