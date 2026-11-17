---
kind: spec
policies: [pii-in-logs]
---
# Spec: claims status self-service

## Requirements

### R1: A customer can see the status of their own claim

### R2: Status is one of four states

Received, in review, approved, paid.

### R3: Status refreshes every 60 seconds

### R4: The response holds no field beyond the status

## Design

The portal's status panel reads one endpoint on claims-api, which reads claims-core and caches the answer.

## How each constraint in the intent is met

| Constraint | Met by |
|---|---|
| Only claims-api talks to claims-core | The panel reads one endpoint on claims-api and never calls claims-core. |
| No personal data beyond the status leaves claims-api | R4. The response holds the status and nothing else. |

## Open questions from intent

### Q1: Do third-party loss adjusters need access too?
- answer: carried

Not settled here. It becomes the child intent `loss-adjuster-access`.

## Areas of concern

### C1: claims-core allows 50 requests a second
- owner: platform team

The endpoint must cache reads and never poll.
