---
kind: spec
policies: [pii-in-logs]
---
# Spec: claims status self-service

## Requirements

### R1: A customer can see the status of their own claim
- area: status

### R2: Status is one of four states
- area: status

Received, in review, approved, paid.

### R3: Status refreshes every 60 seconds
- area: freshness

### R4: The response holds no field beyond the status
- area: privacy

## Design

The portal's status panel reads one endpoint on claims-api, which reads claims-core and caches the answer.

## Open questions from intent

### Q1: Do third-party loss adjusters need access too?
- answer: carried

Not settled here. It becomes the child intent `loss-adjuster-access`.

## Areas of concern

### C1: claims-core allows 50 requests a second
- owner: platform team

The endpoint must cache reads and never poll.
