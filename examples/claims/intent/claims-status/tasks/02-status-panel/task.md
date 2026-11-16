---
kind: task
step: 2
delivers: [R1, R3]
depends: [01-status-endpoint]
size: 5
---
# Task: the status panel

## What to build

A panel on the claim page that shows the status and refreshes it.

## Done when

- The panel shows the state the endpoint returns.
- It refreshes every 60 seconds and never more often.
