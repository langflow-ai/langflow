# Desktop OAuth registrations: Langflow-owned public clients by default

Status: accepted
Decision ID: desktop-oauth-ownership
Applies to: matrices/google.json, matrices/microsoft.json, matrices/slack.json (`oauth_app_owner_by_context.desktop`); the `desktop` deployment context of every included action; the INT-5 named OAuth profiles
Owners (sign-off roles): hosted-app owner, langflow-base owner, release owner
Last verified: 2026-09-02

## Context

The gate froze `oauth_app_owner_by_context` on 2026-09-01 as Langflow-owned for hosted and customer-owned for
self-managed, Desktop, and headless. The self-managed cell is forced by the providers: an OAuth registration must
list its redirect URIs, a self-managed instance lives at a URL Langflow cannot know, and a Langflow-operated redirect
relay is out of scope for 1.13. The Desktop cell was inherited from self-managed because Desktop runs the same
backend on `localhost:7860` and returns through the same callback route.

On 2026-09-02 the release owner asked why Desktop, which is wrapped OSS from Langflow's side, does not get the same
zero-setup connect as hosted. From the providers' side Desktop is a native application, and every wave-1 provider
supports shipping a vendor-owned public client inside a distributed native application: the redirect is a loopback
address that is the same on every install, so one Langflow-owned registration serves every Desktop user. This record
flips the Desktop default and keeps customer-owned registrations as the override that self-managed already has.
Blocks the Desktop entries of INT-5 and the Desktop runbook of INT-14.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | Google installed applications, which include the "Desktop app" client type, "cannot keep secrets"; the loopback redirect is `http://127.0.0.1:port` or `http://[::1]:port` with the app listening locally; PKCE is recommended (`google-oauth2-native-app`) | https://developers.google.com/identity/protocols/oauth2/native-app | 2026-09-02 | high |
| 2 | Google app verification is tied to the project's OAuth consent screen (brand, authorized domains, project contact), not to an individual client ID, so a Desktop client created in the hosted project carries the hosted app's brand and sensitive-scope verification (`google-oauth-verification-requirements`) | https://support.google.com/cloud/answer/13464321 | 2026-09-02 | high |
| 3 | Microsoft public client applications "can't have client secrets"; an app registration that serves a public client enables the public client flow (`entra-public-client-apps`) | https://learn.microsoft.com/en-us/entra/identity-platform/msal-client-applications | 2026-09-02 | high |
| 4 | One Entra app registration carries redirect URIs for several platforms (Web; Mobile and desktop applications); `http://localhost` is valid, the port is ignored when matching localhost redirect URIs, `127.0.0.1` is preferred, and an `http` loopback URI is added through the manifest `replyUrlsWithType` attribute (`entra-reply-url`) | https://learn.microsoft.com/en-us/entra/identity-platform/reply-url | 2026-09-02 | high |
| 5 | Slack: enabling PKCE marks the app a public client and is one-way; PKCE-opted localhost redirects count as desktop; "Desktop redirects are not allowed to request bot scopes" (`slack-pkce`) | https://docs.slack.dev/authentication/using-pkce/ | 2026-09-01 | high |
| 6 | Commercially distributed non-Marketplace Slack apps get 1 request per minute with a 15-message cap on `conversations.replies` and `conversations.history` (`slack-conversations-replies`) | https://docs.slack.dev/reference/methods/conversations.replies | 2026-09-01 | high |
| 7 | Langflow Desktop is a Tauri v2 wrapper that runs the backend on `localhost:7860`, so the OAuth return is the self-managed callback route (`frontend-surfaces.md` finding 3, `connection-contract.md` question 12.b.7) | https://github.com/langflow-ai/langflow-desktop | 2026-09-01 | high |

## Options

### Option A: Keep Desktop customer-owned (the 2026-09-01 default)

Pros: no additional Langflow-operated registrations; the Desktop guide is the self-managed guide.
Cons: every Desktop user must create a Google Cloud project, an Entra app registration, and a Slack app before the
first connect, which is the setup hosted exists to remove; Desktop is the deployment least likely to have an
administrator to do it; the least-operated context gets three provider setup guides.
Cost: none in engineer-weeks; the adoption cost lands on every Desktop user.

### Option B: Langflow-owned public clients for Desktop, customer-owned as the override (selected)

Google: a "Desktop app" client in the hosted Google Cloud project with an embedded client id, PKCE, and the loopback
redirect (fact 1); it carries the hosted brand and sensitive-scope verification (fact 2); the restricted-scope
decision applies unchanged, so Desktop gets the same five actions as hosted.
Microsoft: the hosted app registration gains a Mobile and desktop applications platform with the `127.0.0.1`
loopback redirect and public client flows enabled (facts 3 and 4); one registration, one publisher verification.
Slack: a second Langflow-owned Slack app with PKCE enabled, because PKCE opt-in is one-way and cannot share the
hosted confidential-client app (fact 5); bot actions stay absent from the `desktop` context (fact 5).
The customer-owned override is the path self-managed uses, so Workspace or Entra tenants that require their own
registration lose nothing.
Pros: Desktop connect is zero-setup; the authentication matrix collapses to Langflow-owned (hosted, Desktop) versus
customer-owned (self-managed, headless); INT-14 still tests two registration modes times two client types.
Cons: the hosted-app owner operates one more Slack app and two more redirect entries; the hosted Google app's user
cap and verification status now also gate Desktop; the Desktop Slack app is a distributed non-Marketplace app unless
listed, so `conversations.replies` runs at the reduced tier (fact 6), the same question hosted already carries.
Cost: about 0.25 engineer-weeks in INT-5 for the Desktop entries in the named OAuth profiles and the registration
selector; no calendar lead time beyond hosted's, because the Google and Microsoft verifications are shared.

### Option C: Langflow-owned for Desktop with no customer-owned override

Rejected. Workspace and Entra tenants that block third-party applications, and any tenant that wants an Internal
user type project for the 1.14 restricted-scope profile, need their own registration on Desktop as well.

## Decision

Option B. `oauth_app_owner_by_context.desktop` is `langflow` in all three matrices and
`oauth_client_type_by_context.desktop` stays `public`. INT-5 ships Desktop entries in the named OAuth profiles
(`connection-contract.md` section 8, `owner_by_context` and `client_type_by_context`) that point at the
Langflow-owned public clients, with the customer-owned registration selectable per provider exactly as on
self-managed. Slack bot actions remain absent from the `desktop` deployment context. The Desktop build embeds client
ids only; it never embeds a client secret for any provider (facts 1 and 3).

## Consequences

- Matrices: the three `desktop` owner cells flip to `langflow`. No action row changes, because the Desktop callback
  mechanism (`loopback_redirect`) and client type (`public`) were already recorded; `microsoft.json` gains the
  `entra-public-client-apps` source.
- `connection-contract.md` question 12.b.7, `frontend-surfaces.md` finding 3, and the Decision and Consequences of
  `decisions/substrate-slack.md` reference this record.
- `estimate.md`: INT-5 rises from 5 to 5.25 engineer-weeks (total 48.75); two Desktop rows join the external
  lead-time table.
- INT-14 hosted-app runbook: create the Google Desktop client in the hosted project; add the Entra Mobile and desktop
  applications platform and enable public client flows; create and PKCE-enable the second Slack app; record the
  three client ids in the bundles' provider profiles.

## Re-open trigger

- A provider begins requiring per-installation registration for native applications or withdraws loopback redirects
  for public clients, or
- the hosted Google application enters a state (user cap, verification lapse) that Desktop must not inherit, or
- product decides Desktop must not depend on Langflow-operated registrations.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| hosted-app owner | | | |
| langflow-base owner | | | |
| release owner | Eric Hare | 2026-09-02 | #14906 (confirmed in the planning session) |
