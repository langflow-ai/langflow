# Re-issued estimate for TRG-1 through TRG-8

Status: last issued 2026-09-05; criterion 9 reopened 2026-09-10 pending consent sizing and a revised total
Owners (sign-off roles): release owner
Last verified: 2026-09-10

TRG-1's last exit criterion. The original ticket breakdown summed to 34 engineer-weeks including TRG-1. The numbers
below are the last issued baseline, applying the gate's findings ticket by ticket; every delta names its record or
fact. The frontend consent work clarified on 2026-09-10 still needs sizing, so the frontend and total estimates
must be re-issued before criterion 9 closes. The recorded 2026-09-05 sign-off applies only to that baseline.

**Release target.** The scaffold in this directory was written as a 1.14 candidate and
[`../dedicated-integrations/estimate.md`](../dedicated-integrations/estimate.md) excludes triggers from the 1.13
total. The release owner decided on 2026-09-04 that the triggers epic is 1.13 scope and that every TRG ticket gets a
pull request now. That decision supersedes the "1.14 candidate" framing in the README, the exclusion line in the
1.13 estimate, and the deferral in `../dedicated-integrations/triggers-deferred.md`; all three are amended in this
pull request, each with a dated "release owner decision, 2026-09-04" note, rather than left to contradict this
record. The 48.75 engineer-week figure for INT-1 through INT-14 is unchanged - the triggers work is additional to it,
not inside it, and Risk 7 of the governing plan is answered by adding capacity rather than by re-scoping the actions
release.

Assumptions: the accepted records in `decisions/` hold (separate listener process with a subprocess mode;
at-least-once collapsed in the ledger; no relay); one engineer per stream; TRG-3 and TRG-4 run in parallel on TRG-2;
TRG-5 and TRG-6 run in parallel once TRG-3, TRG-4 and their bundles exist.

## Per ticket

| Ticket | Jira | Original | Last issued (2026-09-05) | Delta | Why |
|---|---|---|---|---|---|
| TRG-1 Discovery gate | LE-2480 | 3 | 3 | 0 | as sized; this pull request |
| TRG-2 Trigger entity, ledger, dispatcher | LE-2481 | 6 | 6.5 | +0.5 | one migration now creates all five tables (`trigger-contract.md` section 1) so TRG-3 and TRG-4 add none; the dispatcher needs its own background-execution frame source, because the default one cannot load a pinned `FlowVersion` and is not installed in a fresh process |
| TRG-3 Listener process | LE-2479 | 6 | 6.5 | +0.5 | `decisions/process-model.md` selects **both** shapes: the separate service ships first and the lifespan subprocess mode is a second stacked branch with its own single-worker guard and Desktop verification |
| TRG-4 Push ingress and subscriptions | LE-2478 | 4 | 4.5 | +0.5 | four verifiers rather than three (Slack signature, Graph `validationToken` plus `clientState`, Google channel token, generic HMAC), a per-route body cap the global 1 GiB limit does not give, a registration-level Slack signing secret, and the new `provider_signed` access mode with its checker pairing |
| TRG-5 Slack on both tracks | LE-2483 | 3 | 3.5 | +0.5 | the third named Slack profile for the app-level token (`trigger-contract.md` section 6) and the recorded-payload contract tests proving the Events API and Socket Mode normalize identically |
| TRG-6 Microsoft and Google sources | LE-2484 | 5 | 5.5 | +0.5 | `decisions/self-managed-ingress.md` makes Track B mandatory for Google, so Calendar and Drive each ship a poll adapter as well as a push channel; the push and poll dedupe-key equality tests are new work the ticket text did not size |
| TRG-7 Frontend | LE-2485 | 4 | 5.5 | +1.5 | the event inspector with replay lineage and the transport/latency label are net new (`frontend-surfaces.md` B4, B5, B6); seven locale catalogs; an axe baseline plus a stateful spec; and the interim connection field that INT-8 later replaces |
| TRG-8 Governance, audit, GA validation | LE-2482 | 3 | 4.5 | +1.5 | five deployment contexts times six sources is a bigger validation matrix than the ticket assumed, and the 24-hour chaos soak plus the in-place upgrade run are calendar work with fixed external setup |
| **Total** | | **34** | **39.5** | **+5.5** | |

## Sequencing

| Wave | Tickets | Gate |
|---|---|---|
| 1 | TRG-1 (this pull request), TRG-2 | TRG-2 bases on the INT-5 branch and is not rebased onto INT-6; family key names are agreed with INT-6 rather than merged |
| 2 | TRG-3, TRG-4, TRG-7 on TRG-2 | TRG-3 and TRG-4 are siblings; a branch that needs both needs a merge revision because each would otherwise chain its own migration |
| 3 | TRG-5 (TRG-3 + TRG-4 + INT-12), TRG-6 (TRG-3 + TRG-4 + INT-10 / INT-11) | bundle branches must exist first; TRG-6 ships as a Microsoft pull request and a Google pull request rather than one |
| 4 | TRG-8 | needs every source and every packaging shape to exist before the context matrix can be filled |

Consent sequencing clarification, 2026-09-10: TRG-7's interim connection field includes the explicit
`allow_non_interactive` control and recovery path in `frontend-surfaces.md` B9. Provider-trigger enablement depends
on INT-4's authenticated connection-update API as well as TRG-2. INT-8 later owns the permanent Connections-page
control. The frontend owner must include consent, withdrawal, and non-owner denial in the existing TRG-7 review
and sizing before sign-off. Criterion 9 remains open until that review and the release owner's re-issued frontend
and total estimates are recorded; the table above remains the last issued baseline.

## External lead times (calendar risk, not engineer-weeks)

| Dependency | Context | Lead time | Source |
|---|---|---|---|
| Google notification-domain verification for the hosted ingress host | hosted | Search Console verification, minutes once DNS control exists; repeated if the hostname changes | `matrices/google-events.json` source `calendar-push` |
| Slack Marketplace listing | hosted | Slack review, weeks; already a 1.13 dependency for the action rate tier | `../dedicated-integrations/estimate.md` |
| Customer Cloud project with a Pub/Sub topic and a publish grant for the Gmail service account | self-managed, desktop | customer task; blocks every Gmail trigger | `matrices/google-events.json` source `gmail-push` |
| Public HTTPS ingress on a self-managed instance | self-managed | customer task; not having one costs latency, not function (`decisions/self-managed-ingress.md`) | this gate |
| Teams event-source scope and permission review | any | not sized; Teams remains excluded pending separate discovery; the former metered billing model is no longer a prerequisite | `matrices/microsoft-events.json` sources `graph-teams-notifications` and `graph-teams-licenses` |
| Two Slack apps for the opt-in live suite (a distributed confidential app and a customer-owned Socket Mode app) plus a workspace, with credentials in CI custody | validation | no such secret exists in `scripts/ci` today | TRG-5, TRG-8 |

## What this estimate does not include

A Langflow-operated relay (forbidden by `decisions/self-managed-ingress.md`); Track A on `lfx serve` (excluded by
`decisions/process-model.md`); Graph rich notifications and their certificate lifecycle (deferred in
`matrices/microsoft-events.json`); Teams as an event source; Discord, which the `origin/mock-orchestra` precedent
built but no wave-1 ticket carries; and the Enterprise approval, quota and audit-query surfaces beyond the plugin
seams TRG-8 registers.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| release owner | Eric Hare | 2026-09-05 | #14911 |
