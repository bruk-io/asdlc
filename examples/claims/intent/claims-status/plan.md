---
kind: plan
---
# Plan: claims status self-service

## Files that change

- claims-api/routes/status.py (new)
- claims-api/tests/test_status.py (new)
- portal/src/claims/StatusPanel.tsx (new)

## Order of work

### Step 1: Add the status endpoint behind existing auth
- delivers: R1, R2, R4

### Step 2: Build the status panel on a 60-second cache
- delivers: R1, R3

### Step 3: Decide access for loss adjusters
- intent: loss-adjuster-access

## Risks

claims-core rate-limits at 50 requests a second, so the panel must read through the cache (C1).

## Proof

The endpoint's tests cover the four states (R2) and fail on any extra field (R4).
