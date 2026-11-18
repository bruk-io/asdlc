#!/bin/sh
# A repository where the intent, claim-steps, and its spec are accepted, and its
# plan is written but not accepted: the plan is on its own branch and not on main.
# The run starts on that branch, where writing the plan left it.
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

### C1: claims-core allows 50 requests a second, and nobody has load tested the portal against it
- owner: the claims team

Listing every step for a page of claims calls `fetch_claim` once for each claim. A busy morning may go over the limit.
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

Steps 1 and 2 need nothing from each other. Step 3 needs step 1.

### Step 1: The portal shows a claim's step by name
- delivers: R1

Add a function `step_name(step)` to `claims_gateway.py`. It gives a step's name as the portal shows it: "Assessed" for "assessed". `status_line` in `portal/adjuster_view.py` returns `step_name` of the claim's step in place of "In progress". The test in `tests/test_adjuster_view.py` expects "Assessed" for claim `c-1`.

### Step 2: An adjuster is shown no step for a claim that is not theirs
- delivers: R3

`fetch_claim` in `claims_gateway.py` takes the adjuster's name as a second argument, and returns `None` for a claim assigned to someone else. `status_line` in `portal/adjuster_view.py` takes the name, passes it on, and returns an empty string when it gets `None`. Add a test for another adjuster's claim to `tests/test_adjuster_view.py`. This step needs nothing the other steps build.

### Step 3: The portal lists every step, with the claim's own marked
- delivers: R2

Add a function `step_list(claim_id)` to `portal/adjuster_view.py`. It goes through `STEPS` from `claims_gateway.py` in order, names each step with `step_name`, and marks the claim's own. It needs the `step_name` function step 1 adds, and cannot be built before it. Add a test to `tests/test_adjuster_view.py`.

## Risks

Step 3 is the riskiest. Listing every step for a page of claims calls `fetch_claim` once for each claim, and claims-core allows 50 requests a second (C1). That is a risk to watch, and no step waits on it. `export_row` in `claims_gateway.py` must not change, because the finance system reads the nightly export.

## Proof

- R1: `test_an_open_claim_shows_its_step` in `tests/test_adjuster_view.py`.
- R2: `test_every_step_is_listed_in_order` in `tests/test_adjuster_view.py`.
- R3: `test_another_adjusters_claim_shows_no_step` in `tests/test_adjuster_view.py`.
- `python3 -m unittest discover tests` passes.
MD
git add -A
git commit --quiet -m "Plan: adjusters can see which step a claim is at"
