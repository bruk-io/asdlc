#!/bin/sh
# A repository whose main holds an accepted intent, claim-steps, its accepted spec
# and its accepted plan of two steps. The spec's C1 is an open product question,
# and step 2 of the plan says it waits on C1. The step is not handed over: no
# child intent exists. There are no tasks yet.
#
# asdlc is not here when this runs, so the documents are written out in full.
# tests/test_evals.py runs this script and lints what it builds.
set -eu

git init --quiet -b main .
git config user.name "Dana Okafor"
git config user.email dana.okafor@example.com

mkdir -p portal tests
printf '# Claims portal\n\nThe portal adjusters use to work a claim.\n\nRun the tests with `python3 -m unittest discover tests`.\n' >README.md

cat >claims_gateway.py <<'PY'
"""Reads a claim from claims-core for the adjuster portal."""

# The steps a claim goes through, in order. claims-core stores the step by name.
STEPS = ("received", "assessed", "approved", "paid")


def fetch_claim(claim_id: str) -> dict[str, str]:
    """Give one claim as claims-core holds it: its id, its adjuster and its step."""
    return {"id": claim_id, "adjuster": "a.osei", "step": "assessed"}


def export_row(claim: dict[str, str]) -> str:
    """Give the claim as one line of the nightly export the finance system reads."""
    return f"{claim['id']},{claim['step']}"
PY

cat >portal/adjuster_view.py <<'PY'
"""What an adjuster sees for one claim."""

from claims_gateway import fetch_claim


def status_line(claim_id: str) -> str:
    claim = fetch_claim(claim_id)
    return "Paid" if claim["step"] == "paid" else "In progress"
PY

cat >tests/test_adjuster_view.py <<'PY'
import unittest

from portal.adjuster_view import status_line


class StatusLine(unittest.TestCase):
    def test_an_open_claim_is_in_progress(self):
        self.assertEqual(status_line("c-1"), "In progress")
PY

git add -A
git commit --quiet -m "Start"

git switch --quiet -c intent/claim-steps
mkdir -p intent/claim-steps
cat >intent/claim-steps/intent.md <<'MD'
---
kind: intent
author: Dana Okafor
---
# Intent: adjusters can see which step a claim is at

## Problem

Our adjusters keep phoning the help desk to ask where a claim is. The adjuster portal only says "In progress" from the day a claim is opened until the day it is paid.

## Proposed outcome

- An adjuster can see which step a claim is at in the adjuster portal, without phoning anyone.

## Affected users and systems

Adjusters and the help desk. The adjuster portal. The claims team owns the claims data, and the finance team owns the nightly export.

## Constraints

- The nightly export to the finance system does not change.
- An adjuster sees only the claims assigned to them.

## Open questions

### Q1: What steps does a claim go through, and in what order?
MD
git add -A
git commit --quiet -m "Intent: adjusters can see which step a claim is at"
git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #1 from acme/intent/claim-steps" intent/claim-steps
git branch --quiet -D intent/claim-steps

git switch --quiet -c spec/claim-steps
cat >intent/claim-steps/spec.md <<'MD'
---
kind: spec
---
# Spec: adjusters can see which step a claim is at

## Requirements

### R1: The adjuster portal shows the step a claim is at, by name

### R2: The portal lists every step in the order claims-core holds them, with the claim's own step marked

### R3: An adjuster who asks for a claim that is not assigned to them is shown no step

## Design

- `claims_gateway.py` holds the steps in order as `STEPS`, and `fetch_claim` returns a claim's step and its adjuster. `fetch_claim` will take the adjuster's name as well, and return nothing for a claim assigned to someone else (R3).
- `status_line` in `portal/adjuster_view.py` returns the step's name in place of "In progress" (R1). A new function beside it lists every step in order and marks the claim's own (R2).
- `export_row` in `claims_gateway.py` is not touched.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The nightly export to the finance system does not change. | `export_row` is not touched, and it reads the same claim it always did. |
| An adjuster sees only the claims assigned to them. | R3. |

## Open questions from intent

### Q1: What steps does a claim go through, and in what order?
- answer: answered

From the code: `STEPS` in `claims_gateway.py` is received, assessed, approved, paid.

## Areas of concern

### C1: Nobody has decided whether a team lead counts as assigned to their adjusters' claims
- owner: the claims team

R3 says an adjuster who asks for a claim that is not assigned to them is shown no step. Team leads open their adjusters' claims every day. Whether the portal should show a lead the step of such a claim is a decision about what the product does, and the claims team has not made it.
MD
git add -A
git commit --quiet -m "Spec: adjusters can see which step a claim is at"

git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #2 from acme/spec/claim-steps" spec/claim-steps
git branch --quiet -D spec/claim-steps

git switch --quiet -c plan/claim-steps
cat >intent/claim-steps/plan.md <<'MD'
---
kind: plan
---
# Plan: adjusters can see which step a claim is at

## Files that change

- claims_gateway.py
- portal/adjuster_view.py
- tests/test_adjuster_view.py

## Order of work

### Step 1: The portal shows a claim's step by name, and lists every step
- delivers: R1, R2

Add a function `step_name(step)` to `claims_gateway.py`. It gives a step's name as the portal shows it: "Assessed" for "assessed". `status_line` in `portal/adjuster_view.py` returns `step_name` of the claim's step in place of "In progress". Add a function `step_list(claim_id)` beside it that goes through `STEPS` from `claims_gateway.py` in order, names each step with `step_name`, and marks the claim's own. `tests/test_adjuster_view.py` gains a test for each.

### Step 2: An adjuster is shown no step for a claim that is not theirs
- delivers: R3

This step waits on C1 in the spec. Nobody has decided whether a team lead counts as assigned to their adjusters' claims, so nobody can say yet which claims `fetch_claim` in `claims_gateway.py` should refuse. It cannot be built until the claims team decides.

## Risks

Step 2 is the riskiest: what it builds depends on a decision the claims team has not made (C1). `export_row` in `claims_gateway.py` must not change, because the finance system reads the nightly export.

## Proof

- R1: `test_an_open_claim_shows_its_step` in `tests/test_adjuster_view.py`.
- R2: `test_every_step_is_listed_in_order` in `tests/test_adjuster_view.py`.
- R3: `test_another_adjusters_claim_shows_no_step` in `tests/test_adjuster_view.py`.
- `python3 -m unittest discover tests` passes.
MD
git add -A
git commit --quiet -m "Plan: adjusters can see which step a claim is at"

git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #3 from acme/plan/claim-steps" plan/claim-steps
git branch --quiet -D plan/claim-steps
