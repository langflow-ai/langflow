# Triggers and webhooks: deferred track

Status: deferred, then re-opened 2026-09-04 by release owner decision - see "Amendment" below
Owners (sign-off roles): release owner, platform owner
Last verified: 2026-09-01

## What this record is

The 1.13 plan separates actions from triggers (Scope Boundary 1). Persistent listeners, polling, durable delivery,
replay, deployment binding, conversation correlation, and trigger-driven pause/resume are not 1.13 requirements.
The discovery gate's exit criterion "fold in the trigger/webhook findings as a separate, deferred track" is met by
this record, which carries the findings available in the governing plan, fixes the boundary, and states what still
needs provider-specific discovery. It does not claim that the deferred provider transport investigation is done.

## Findings carried from the governing plan

- Request/response actions and persistent triggers are separate lifecycle and delivery products. No wave-1 action
  may open a listener, create a subscription, or imply durable event delivery.
- Persistent listeners, polling, durable delivery, replay, deployment binding, conversation correlation, and
  trigger-driven pause/resume remain deferred.
- The executing-identity rule is binding for future triggers: interactive user connections resolve only for the
  owner or an explicit share; flow-owner, deployment-owner, and other non-interactive execution may use a user
  connection only with that connection's explicit opt-in; anonymous execution never resolves a user connection.
- OAuth for an unauthenticated public-flow caller is a separate initiative. It requires one-time state and PKCE,
  tenant and execution binding, and an explicit end-user identity model rather than borrowing the flow owner's
  connection.
- Provider event transports must be discovered independently and must not be pre-empted by fields added for the
  action release.

## What remains for deferred discovery

- Provider event sources: Gmail push notifications (Pub/Sub), Microsoft Graph change notifications and
  subscriptions, Slack Events API and Socket Mode.
- Delivery semantics: at-least-once vs exactly-once, replay windows, dead-lettering.
- Binding a trigger to a deployment or flow version, and correlating a triggered run to a conversation.
- Provider subscription ownership, renewal, public-ingress requirements, and tenant-specific rate limits.

## Interaction with the actions release

Wave-1 actions must not pre-empt trigger design: no action component may open a long-lived listener, and the
connection record must not grow trigger-specific fields in 1.13.

## Re-open trigger

- A written trigger/webhook findings document exists, or
- A customer commitment names a trigger-driven flow for a dated release, or
- Two of the three providers' event-delivery mechanisms are confirmed usable from a self-managed instance without
  a public ingress (otherwise the hosted-only constraint changes the design).

Re-verify by: the 1.14 planning gate.

## Amendment: re-opened 2026-09-04 (release owner decision)

The release owner decided on 2026-09-04 that the triggers epic is 1.13 scope and that every TRG ticket gets a pull
request now. This record is therefore superseded as a *deferral*, and is kept as the statement of the boundary it
fixed. Its re-open trigger is met on two of its three clauses, verified 2026-09-05:

| Clause | State |
|---|---|
| A written trigger/webhook findings document exists | partly: [`../dedicated-integrations-triggers/findings/2026-09-listeners.md`](../dedicated-integrations-triggers/findings/2026-09-listeners.md) carries the evidence pack and awaits the platform owner's authored sections |
| A customer commitment names a trigger-driven flow for a dated release | not met; the 1.13 decision does not rest on one |
| Two of three providers' event delivery confirmed usable from a self-managed instance without public ingress | **met, three of three**: Slack Socket Mode, Microsoft Graph delta queries, and Google sync-token/page-token polling plus Cloud Pub/Sub pull, recorded in [`../dedicated-integrations-triggers/decisions/self-managed-ingress.md`](../dedicated-integrations-triggers/decisions/self-managed-ingress.md) and machine-checked by `check_capability_matrices.py --design-root design/dedicated-integrations-triggers` |

What does not change: the boundary this record fixed under "Interaction with the actions release" still binds every
wave-1 action. No action component opens a listener, and the connection record grows no trigger-specific fields -
trigger state lives on the `trigger` and `trigger_subscription` tables
([`../dedicated-integrations-triggers/trigger-contract.md`](../dedicated-integrations-triggers/trigger-contract.md)
section 1). The discovery this record said still had to happen is done, in
[`../dedicated-integrations-triggers/`](../dedicated-integrations-triggers/README.md).

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| platform owner | | | |
| release owner | Eric Hare | 2026-09-01 | #14906 (confirmed in the planning session) |
