#!/bin/sh
# A repository whose main holds two accepted intents and one accepted spec.
#
# claim-status is older and has a spec. Its R1 is in force: the portal shows a claim
# as "In progress" until it is paid. claim-steps is new, has no spec, and ends that
# requirement. Its two constraints cannot both hold: a date a step is expected to
# finish is an estimate.
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

# The older intent and its spec, each accepted by a merge.
git switch --quiet -c intent/claim-status
mkdir -p intent/claim-status
cat >intent/claim-status/intent.md <<'MD'
---
kind: intent
author: Dana Okafor
---
# Intent: adjusters can tell an open claim from a paid one

## Problem

An adjuster cannot tell from the portal whether a claim has been paid.

## Proposed outcome

- The adjuster portal shows whether a claim is open or paid.

## Affected users and systems

Adjusters. The adjuster portal.

## Constraints

- An adjuster sees only the claims assigned to them.

## Open questions
MD
git add -A
git commit --quiet -m "Intent: adjusters can tell an open claim from a paid one"
git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #1 from acme/intent/claim-status" intent/claim-status
git branch --quiet -D intent/claim-status

git switch --quiet -c spec/claim-status
cat >intent/claim-status/spec.md <<'MD'
---
kind: spec
---
# Spec: adjusters can tell an open claim from a paid one

## Requirements

### R1: The adjuster portal shows a claim as "In progress" from the day it is opened until the day it is paid

### R2: The adjuster portal shows a paid claim as "Paid"

## Design

`portal/adjuster_view.py` reads the claim through `claims_gateway.py` and prints one of the two words.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| An adjuster sees only the claims assigned to them. | The portal's existing sign-in. Nothing here widens it. |

## Open questions from intent

## Areas of concern
MD
git add -A
git commit --quiet -m "Spec: adjusters can tell an open claim from a paid one"
git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #2 from acme/spec/claim-status" spec/claim-status
git branch --quiet -D spec/claim-status

# The new intent, accepted, with no spec yet.
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

Adjusters and the help desk. The adjuster portal. The claims team owns the claims data, and compliance owns what the portal may say about dates.

## Constraints

- Every step is shown with the date it is expected to finish.
- The portal never shows a date that is an estimate.

## Open questions
MD
git add -A
git commit --quiet -m "Intent: adjusters can see which step a claim is at"
git switch --quiet main
git merge --quiet --no-ff -m "Merge pull request #3 from acme/intent/claim-steps" intent/claim-steps
git branch --quiet -D intent/claim-steps
