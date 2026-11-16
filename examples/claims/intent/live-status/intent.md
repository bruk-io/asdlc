---
kind: intent
author: M. Chen
---
# Intent: claim status updates as it happens

## Problem

A customer who has just been told on the phone that their claim was approved still sees "in review" for up to a minute.

## Proposed outcome

The portal shows a new status within seconds of the change.

## Affected users and systems

Customers, the portal, claims-api, claims-core's event feed.

## Constraints

The 50 requests a second limit on claims-core still holds.

## Open questions

None.
