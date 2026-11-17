---
kind: spec
---
# Spec: claim status updates as it happens

## Requirements

### R1: Status updates within 2 seconds of a change
- replaces: claims-status.R3

### R2: Push is used where the browser supports it

## Design

claims-api subscribes to claims-core's event feed and pushes to open panels.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| The 50 requests a second limit on claims-core still holds | claims-api listens to the event feed, so a status change costs claims-core no request. |
