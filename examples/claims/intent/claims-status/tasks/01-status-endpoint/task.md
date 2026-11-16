---
kind: task
step: 1
delivers: [R1, R2, R4]
size: 3
---
# Task: the status endpoint

## What to build

`GET /claims/{id}/status` on claims-api, behind the existing customer auth.

## Done when

- The endpoint returns one of the four states for the caller's own claim.
- A claim that is not the caller's returns 404.
- The response has no field beyond the status.
