#!/bin/sh
# A repository whose main holds an accepted intent, claim-steps, and its accepted
# spec. The spec carried one question to C1, and its R2 cannot be built until that
# is answered. There is no plan yet.
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

### Q1: Do loss adjusters from outside the company, who have no portal account, need to see this too?
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

### R2: The step is shown to every adjuster who works the claim, and to nobody else

Who works a claim is not settled: see C1.

## Design

- `status_line` in `portal/adjuster_view.py` returns the step's name in place of "In progress" (R1). `STEPS` in `claims_gateway.py` holds the names.
- `fetch_claim` in `claims_gateway.py` will take the name of whoever is asking, and return nothing for someone who does not work the claim (R2). Today a claim has one `adjuster`. What the check compares against waits on C1.
- `export_row` in `claims_gateway.py` is not touched.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The nightly export to the finance system does not change. | `export_row` is not touched. |
| An adjuster sees only the claims assigned to them. | R2. |

## Open questions from intent

### Q1: Do loss adjusters from outside the company, who have no portal account, need to see this too?
- answer: carried

Carried to C1. Nothing in the intent or the code says.

## Areas of concern

### C1: Whether loss adjusters from outside the company get to see a claim's step is not decided
- owner: the claims team

They work claims and have no portal account. If they are to see the step, they need a way in, and R2's "every adjuster who works the claim" includes them. If not, R2 is the assigned adjuster alone. The claims team decides.
MD
git add -A
git commit --quiet -m "Spec: adjusters can see which step a claim is at"

git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #2 from acme/spec/claim-steps" spec/claim-steps
git branch --quiet -D spec/claim-steps
