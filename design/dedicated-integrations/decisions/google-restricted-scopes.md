# Google restricted scopes on the Langflow-owned hosted app: CASA or avoid

Status: accepted
Decision ID: google-restricted-scopes
Applies to: matrices/google.json; scopes gmail.readonly, drive.readonly, drive.metadata.readonly; actions google.gmail.search, google.drive.list, google.drive.fetch
Owners (sign-off roles): hosted-app owner, release owner, Enterprise owner, langflow-base owner
Last verified: 2026-09-01

## Context

Hosted Langflow ships in 1.13 with a Langflow-owned External Google OAuth application. Any restricted scope on that
application triggers Google's restricted-scope verification and, because the hosted backend accesses the data
through a third-party server, a CASA security assessment with annual recertification. Three wave-1 candidate
actions carry restricted scopes. This record decides, per scope, whether the hosted app accepts CASA or wave 1
avoids the scope, and how self-managed deployments with customer-owned applications are treated. Blocks INT-10 and
the hosted rows of the authentication matrix.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | `gmail.readonly`, `gmail.compose`, `gmail.metadata`, `gmail.modify`, `mail.google.com` are restricted; `gmail.send` is sensitive; `gmail.labels` is non-sensitive | https://developers.google.com/workspace/gmail/api/auth/scopes | 2026-09-01 | high |
| 2 | `drive.readonly`, `drive.metadata.readonly`, `drive` are restricted; `drive.file` is non-sensitive and recommended with the Picker API | https://developers.google.com/workspace/drive/api/guides/api-specific-auth | 2026-09-01 | high |
| 3 | users.messages.list: the `q` parameter "cannot be used when accessing the api using the gmail.metadata scope", so there is no narrower Gmail search scope than `gmail.readonly` | https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list | 2026-09-01 | high |
| 4 | Restricted-scope verification: brand verification first (2-3 business days); CASA under the App Defense Alliance by Google-empanelled assessors when restricted data is accessed "from or through a third-party server"; "can potentially take several weeks"; reverification "at least every 12 months" after the Letter of Assessment | https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification | 2026-09-01 | high |
| 5 | Exemptions: Internal user type projects owned by a Google Workspace or Cloud Identity organization; domain-wide installations still require app verification when restricted or sensitive scopes are used | same | 2026-09-01 | high |
| 6 | Unverified apps face a user cap and an unverified-app screen; Testing publishing status caps at 100 test users with 7-day token expiry | https://support.google.com/cloud/answer/15549945 | 2026-09-01 | high |
| 7 | Sensitive-scope verification (needed for `gmail.send` and the Calendar scopes regardless of this decision) "typically takes 3-5 business days" | https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification | 2026-09-01 | high |
| 8 | The Workspace Gmail and Drive MCP servers request `gmail.readonly`, `gmail.compose`, `drive.readonly`, so the substrate choice does not avoid the restricted tier | https://developers.google.com/workspace/guides/configure-mcp-servers | 2026-09-01 | high |
| 9 | Workspace admins can mark an app Trusted, Limited, Specific Google data, or Blocked; Limited apps cannot reach services an admin marks Restricted; admins can trust internal apps for restricted APIs | https://knowledge.workspace.google.com/admin/apps/control-which-apps-access-google-workspace-data | 2026-09-01 | high |

## Options

### Option A: Accept CASA for the hosted app

Pros: Gmail search and full Drive read ship in wave 1 on hosted.
Cons: several weeks of assessment lead time on the critical path of a release (fact 4), an annual recurring
obligation, assessor cost, and a compliance surface (secure storage of restricted data, documentation) that the
gate cannot size. If the assessment slips, hosted Gmail and Drive read actions slip with it.
Cost: unknown assessor fee; several weeks calendar; annual recert. Not inside any INT ticket today.

### Option B: Avoid restricted scopes on the hosted app in 1.13 (recommended)

The hosted application registers only non-sensitive and sensitive scopes: `gmail.send`, `drive.file`,
`calendar.events`, `calendar.events.readonly`. Consequences per action: Gmail search is excluded from wave 1; Drive
list and fetch ship on `drive.file` only (files the app created or the user opened with it, with the Picker as a
later enhancement).
Pros: only sensitive-scope verification (3-5 business days, fact 7) stands between the hosted app and production;
no recurring assessment; Gmail send, Calendar list, Calendar create, and Drive on app-scoped files still ship.
Cons: Gmail search, the second most requested Google action, is not in wave 1 on any deployment that uses the
default scope set.

### Option C: Avoid on hosted, allow a restricted scope profile on self-managed (deferred variant of B)

Same as B for the hosted app. Self-managed customers with an Internal user type project (fact 5) could enable a
restricted profile on their customer-owned application without CASA; External self-managed projects would own their
own verification. Pros: keeps Gmail search reachable for Workspace-organization customers. Cons: two scope sets
means two component behaviours, two documentation paths, and a policy key to gate the profile; it widens INT-7 and
INT-10 and is not sized. Proposed as the first 1.14 candidate, not as 1.13 scope.

## Decision

Option B, confirmed by the release owner on 2026-09-01.

### https://www.googleapis.com/auth/gmail.readonly

Not requested by the Langflow-owned hosted application in 1.13. `google.gmail.search` is excluded from wave 1 and
carried to the 1.14 candidate list under Option C.
Decision: avoid

### https://www.googleapis.com/auth/drive.readonly

Not requested in 1.13. `google.drive.fetch` ships on `drive.file` only.
Decision: avoid

### https://www.googleapis.com/auth/drive.metadata.readonly

Not requested in 1.13. `google.drive.list` ships on `drive.file` only.
Decision: avoid

## Consequences

- `matrices/google.json`: `google.gmail.search` decision `exclude`; `google.drive.list` and `google.drive.fetch` drop
  their restricted scope entries and keep `drive.file`; `restricted_scope_decisions` entries flip to `avoid`.
- Google wave 1 include set (5 actions): Gmail send, Drive list (app files), Drive fetch (app files), Calendar list,
  Calendar create. Room for up to 3 alternates under the cap of 8; Drive upload (`drive.file`, non-sensitive) and
  Calendar update are the candidates if the release owner wants more Google surface.
- Hosted-app external dependencies: brand verification and sensitive-scope verification only; CASA leaves the
  estimate.
- The auth matrix's hosted Google row records "no restricted scopes" as a constraint of the 1.13 registration.

## Re-open trigger

- Product commits to Gmail search on hosted for a dated release (then Option A starts immediately, given the lead
  time), or
- Google removes `gmail.readonly` or `drive.metadata.readonly` from the restricted list, or
- Option C is sized and accepted for 1.14.

Re-verify by: the 1.14 planning gate, or earlier if Option A is triggered.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| hosted-app owner | | | |
| release owner | Eric Hare | 2026-09-01 | #14906 (confirmed in the planning session) |
| Enterprise owner | | | |
| langflow-base owner | | | |
