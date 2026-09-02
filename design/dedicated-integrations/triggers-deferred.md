# Triggers and webhooks: deferred track

Status: deferred
Owners (sign-off roles): release owner, platform owner
Last verified: 2026-09-01

## What this record is

The 1.13 plan separates actions from triggers (Scope Boundary 1). Persistent listeners, polling, durable delivery,
replay, deployment binding, conversation correlation, and trigger-driven pause/resume are not 1.13 requirements.
The discovery gate's exit criterion "fold in the trigger/webhook findings as a separate, deferred track" is met by
this record, which fixes the boundary and the re-open conditions. No findings have been folded in yet: the
trigger/webhook investigation is not written up in a form this gate could cite, and the release owner chose to
record the track as deferred rather than block the gate on it.

## What was not evaluated

- Provider event sources: Gmail push notifications (Pub/Sub), Microsoft Graph change notifications and
  subscriptions, Slack Events API and Socket Mode.
- Delivery semantics: at-least-once vs exactly-once, replay windows, dead-lettering.
- Binding a trigger to a deployment or flow version, and correlating a triggered run to a conversation.
- Executing identity for trigger-initiated runs. Note: the connection contract (`connection-contract.md`) already
  makes non-interactive use of a user connection a per-connection opt-in; a trigger-initiated run must reuse that
  rule rather than define a new one.

## Interaction with the actions release

Wave-1 actions must not pre-empt trigger design: no action component may open a long-lived listener, and the
connection record must not grow trigger-specific fields in 1.13.

## Re-open trigger

- A written trigger/webhook findings document exists, or
- A customer commitment names a trigger-driven flow for a dated release, or
- Two of the three providers' event-delivery mechanisms are confirmed usable from a self-managed instance without
  a public ingress (otherwise the hosted-only constraint changes the design).

Re-verify by: the 1.14 planning gate.
