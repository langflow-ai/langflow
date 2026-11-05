# Trigger frontend QA acceptance checks

Status: proposed
Owners (sign-off roles): frontend owner, release owner

These checks clarify the [frontend surface contract](frontend-surfaces.md). The complete source and deployment
matrix remains part of TRG-8, as recorded in [the estimate](estimate.md).

## One trigger node per canvas

Check flow creation, PATCH and PUT canvas updates, JSON import, ZIP import, and batch import with two trigger nodes.
The request must fail with a message asking the user to remove the extra nodes. It must not save an invalid canvas
or partially import the other flows in that request. Repeat with one trigger node and with no trigger nodes.

An existing multi-trigger canvas must remain readable. Removing the extra nodes and saving must repair it.
Activating a trigger on the invalid saved canvas must fail before contacting a provider, including creation with
an active state. Schedules created through the API without a canvas node remain supported.

A metadata-only edit to an invalid legacy canvas must still succeed without restarting an errored trigger.
Updating an errored schedule's configuration must not reactivate it until the canvas is repaired.

## Connection recovery

Revoke the selected connection and wait for the trigger to show Needs reconnect. Reconnect must open
Settings → Connections. Reauthorize there, return to the trigger, and wait for Ready to resume. It must remain
stopped until Resume succeeds. Verify that the old credential error no longer appears after reauthorization.

Missing background-run consent uses its own recovery dialog. Saving that consent attempts activation immediately.
Do not count this consent flow as evidence that OAuth recovery resumes automatically.

## Action visibility and permissions

Pause must be absent on a paused trigger, and Resume must be absent on an active trigger. An applicable action
blocked by permissions must remain visible and disabled. Its explanation must be available by keyboard and through
its accessible description. Activating a blocked control must not send a mutation.

With an authorization plugin that supports shared flows, check the same shared trigger as a reader and a writer.
The reader must see the trigger with write actions blocked. A writer without execute permission may pause or
delete it, while Test and Replay remain blocked. Check that an unrelated user cannot see the shared row.
Setting the OSS authorization flag alone does not exercise these permissions because its default implementation
allows every check.

## Rejected webhook requests

Send a request with an invalid signature and one with a stale timestamp. Neither request may start a flow run or
create an accepted event in the owner's history. With authorization auditing enabled, a superuser can inspect
recorded rejection reasons through the audit API. Audit querying must remain unavailable to ordinary owners.

Owner-visible rejection diagnostics are a known limitation. A provider rejection can occur before a trusted
trigger or owner is known, so a registration-wide rejection cannot be attributed to an individual owner's trigger.
Do not expect an empty event inspector to prove that the provider sent no requests.

## Deployment coverage

Use the OSS server for the core frontend pass and a registered authorization plugin for the shared-flow checks
above. Mocked reader/writer capability tests cover rendering and mutation wiring, not a live plugin deployment.

TRG-8 owns the full source and deployment matrix, listener packaging checks, soak, and upgrade validation.
Desktop checks must confirm that triggers fire only while the app is open. Hosted and self-managed checks must
use their supported push or polling transport. Keep these runtime results separate from the frontend test results.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| frontend owner | | | |
| release owner | | | |
