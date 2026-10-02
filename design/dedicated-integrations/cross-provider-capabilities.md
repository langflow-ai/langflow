# Wave-1 capability differences and saved-flow portability

Status: proposed; product and release messaging sign-off pending
Owners (sign-off roles): product owner, release owner, frontend owner, lfx owner
Last updated: 2026-09-09

This comparison records the consequence of the already accepted Google restricted-scope avoidance decision.
It does not claim product approval of parity gaps or promise a broader Google scope profile in 1.13.

| User intent | Google wave 1 | Microsoft wave 1 | Launch/support wording |
|---|---|---|---|
| Search/summarize mailbox content | Unavailable; Gmail search is excluded | Outlook search can return message bodies with delegated `Mail.Read` | Email reading is available for Microsoft; Google supports sending only. Do not advertise generic email-reading parity. |
| Send email | Gmail send | Outlook send | Both execute as the connected user, subject to consent and tenant policy. |
| List/fetch existing files | Only files authorized to the app under `drive.file`; a new connection can return no files | Own OneDrive under `Files.Read`; wider shared-library/site access is conditional on additional scopes | Google is limited to app-authorized files, not an account-wide Drive browser. Microsoft does not request `Files.Read.All` by default. |
| List/create calendar events | Included | Included | Each action exposes its actual identity and scope breadth before consent. |

The product owner owns acceptance of these differences and launch/support copy. INT-10 and INT-11 owners verify
the comparison against their bundles; INT-8 owns the corresponding builder text; INT-14 covers both a fresh Drive
connection and a connection with authorized files. Google Picker is deferred (frontend surface B13), not an
assumed mitigation available in wave 1. See B14 for the required empty-state copy and owner split.

## Saved flows crossing deployment contexts

Option C (a self-managed restricted Google profile) remains deferred and unsized. Before accepting it, INT-3/7/10
must preserve these rules, with INT-8 implementing the builder state and INT-14 testing round trips:

- Keep the stable capability id and `ext:<provider>:<Class>@official` component reference. Deployment policy and
  registration modes are availability metadata; never encode hosted/self-managed scope profiles into class names.
- Import preserves an unavailable node, its inputs, edges and non-secret connection handle. It must not silently
  delete it, swap providers, downgrade to a different action or request a wider grant. Credentials are never exported.
- Show "This action is unavailable in this deployment" with the provider, action and permitted remediation.
  A flow requiring that action cannot run or publish until availability and connection requirements are met;
  the resolver returns `action-unsupported` for an absent capability or `connection-not-authorized` for a policy deny.
- Rebinding an available connection is explicit. Exporting the preserved flow back to a supporting deployment
  retains the original identifiers and graph. INT-3 must retain unavailable-node metadata sufficiently for this
  round trip, even when the destination cannot load the capability implementation.

These are proposed portability requirements for the deferred option, not a claim that Gmail search ships on
self-managed in 1.13. They also guide B11's unavailable-action rendering.

## Sign-off

| Role | Name | Date | PR |
|---|---|---|---|
| product owner | | | |
| release owner | | | |
| frontend owner | | | |
| lfx owner | | | |
