---
kind: intent
author: J. Ortiz
---
# Intent: claims status self-service

## Problem

Customers phone the claims line to ask where their claim is. Most calls end with one sentence read off a screen.

## Proposed outcome

A customer can see the status of their own claim in the portal without calling.

## Affected users and systems

Customers, the claims line, the portal and claims-api.

## Constraints

- Only claims-api talks to claims-core.
- No personal data beyond the status leaves claims-api.

## Open questions

### Q1: Do third-party loss adjusters need access too?
