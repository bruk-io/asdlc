#!/bin/sh
# A repository where the intent, claim-steps, is written but not accepted: it is on
# its own branch and not on main. The run starts on that branch, where capturing the
# intent left it.
#
# asdlc is not here when this runs, so the document is written out in full.
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

Adjusters and the help desk. The adjuster portal.

## Constraints

- An adjuster sees only the claims assigned to them.

## Open questions
MD
git add -A
git commit --quiet -m "Intent: adjusters can see which step a claim is at"
