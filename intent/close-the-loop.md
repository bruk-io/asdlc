# Intent: the board's numbers write the next intent

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-10-23

## Problem

`asdlc stats` gives every stage a number: time to first review, first-pass check success, rework cycles, escaped bugs, gate waits. Nobody watches them. If reviews start waiting twice as long, or more bugs escape, we find out only if someone happens to run `stats` and notices. So what we have is a line that ends at Done, not a loop.

The playbook closes the loop (play 12, our spec's R19): a deterministic script watches a few metrics against bands kept in versioned config, and a breach is diagnosed and written up as an intent that goes back to the start of the loop, where a person decides what to do with it.

## Proposed outcome

- Bands for a few of `asdlc stats`' metrics live in versioned config on the board: the metric, its baseline window, the rules that count as a breach, and what each tier does.
- A deterministic, tested script reads the numbers and decides whether a band is breached. No model decides.
- Tiers follow the spec: log at 1σ, write a read-only diagnosis at 2σ, and at 3σ write a draft intent (later, a pull request into review or a pre-approved runbook).
- Each diagnosis becomes a draft intent in the usual form, with the anomaly and its evidence as the problem. A person triages it: accept, keep for later, or archive. Archived ones are how the bands get tuned.
- `asdlc stats` reports the time from a breach to its draft intent, and the share of those intents that end in a merged fix.

## Affected users and systems

- Engineers on the board, and whoever triages what the detector writes.
- `asdlc stats`, the capture-intent skill, the board's config, and whatever runs the detector on a schedule.

## Constraints

- Detection stays deterministic.
- Start with one or two metrics.
- Runs without a hosted service: on an engineer's machine, in the eval container, or in CI with the same container, without depending on GitHub.
- Agents act only through the board's existing gates, and nothing gets production access.

## Open questions

- [ ] Which metrics first: time to first review, first-pass check success, escaped bugs, or something else?
- [ ] Where does the detector run, and on what schedule, when the board has no CI of its own?
- [ ] What is the baseline while a board is new and has little history?
- [ ] Who triages: the engineer whose machine ran it, a rotation, or a named owner per metric?
- [ ] How does archiving a draft tune the bands: by hand, or recorded and suggested back?
- [ ] Does the 3σ tier's pull request or runbook need play 11 (CI/CD) first, or can it wait until then?
