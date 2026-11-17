#!/bin/sh
# A repository whose main holds one accepted intent, claim-steps, and a little code.
#
# The intent has two constraints and two questions. claims_gateway.py, which the
# intent never mentions, answers the first question. Nothing answers the second.
#
# asdlc is not here when this runs, so the documents are written out in full.
# tests/test_evals.py runs this script and lints what it builds.
set -eu

git init --quiet -b main .
git config user.name "Dana Okafor"
git config user.email dana.okafor@example.com

mkdir -p portal
printf '# Claims portal\n\nThe portal adjusters use to work a claim.\n' >README.md

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

Our adjusters keep phoning the help desk to ask where a claim is. The adjuster portal only says "In progress" from the day a claim is opened until the day it is paid. Last month the help desk logged 412 of these calls.

## Proposed outcome

- An adjuster can see which step a claim is at in the adjuster portal, without phoning anyone.
- Help desk calls asking where a claim is drop below 100 a month.

## Affected users and systems

Adjusters and the help desk. The adjuster portal. The claims team owns the claims data, and the finance team owns the nightly export.

## Constraints

- The nightly export to the finance system does not change.
- An adjuster sees only the claims assigned to them.

## Open questions

### Q1: What steps does a claim go through, and in what order?

### Q2: Do loss adjusters from outside the company, who have no portal account, need to see this too?
MD
git add -A
git commit --quiet -m "Intent: adjusters can see which step a claim is at"

git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #1 from acme/intent/claim-steps" intent/claim-steps
git branch --quiet -D intent/claim-steps
