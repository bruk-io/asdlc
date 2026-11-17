---
kind: plan
---
# Plan: the status panel

Sizing gave this task its own plan: the cache is shared with two other panels.

## Files that change

- portal/src/shared/cache.ts (new)
- portal/src/documents/DocumentsPanel.tsx
- portal/src/claims/StatusPanel.tsx (new)

## Order of work

### Step 1: Move the shared cache out of the documents panel
### Step 2: Build the status panel on it
- delivers: R1, R3

## Proof

The panel's test advances a fake clock and counts one request per 60 seconds.
