---
kind: spec
---
# Spec: claim status updates as it happens

## Requirements

### R1: Status updates within 2 seconds of a change
- replaces: claims-status.R3
- area: freshness

### R2: Push is used where the browser supports it
- area: freshness

## Design

claims-api subscribes to claims-core's event feed and pushes to open panels.
