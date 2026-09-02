# Dedicated Integrations (1.13): discovery gate records

Status: gate artifacts complete on 2026-09-01; the gate remains open pending role-owner sign-offs. Every decision
record is `accepted` by the release owner and the structural checker passes. Gate-close mode
(`check_capability_matrices.py --require-accepted`) intentionally remains red until every declared owner's Name,
Date, and PR cells are complete in both the aggregate table and each record. Wave 1 = Google 5, Microsoft 8, Slack
7 actions.
Jira: LE-2398 "Dedicated Integrations", ticket INT-1.
Last updated: 2026-09-02 (Desktop OAuth registration ownership decision added)

This directory holds the outputs of INT-1, the discovery gate that every other Dedicated Integrations ticket
(INT-2 through INT-14) blocks on. It freezes what 1.13 ships before any provider code is written. The records are
frozen at gate close; from INT-3 onward the bundle-owned capability manifest is the runtime source of truth and
these files are the historical record the checker keeps guarding.

## Exit criteria and where each one lives

| # | Exit criterion (from INT-1) | Artifact | Machine check | Status |
|---|---|---|---|---|
| 1 | Three approved matrices, at most 8 actions each | `matrices/google.json`, `matrices/microsoft.json`, `matrices/slack.json` | `check_capability_matrices.py`: JSON Schema, included-action cap, required fields, enums | Google 5 included (Gmail search excluded), Microsoft 8 included, Slack 7 included (all Web API) |
| 2 | Every scope classified; every restricted scope has a written decision | scope entries in the matrices; `decisions/google-restricted-scopes.md` | classification present and sourced; every scope on an included action tagged `required`, `optional`, or `alternative`; conditional rows carry a structured predicate naming a real action input; at least one scope is required; restricted scopes need a `restricted_scope_decisions` entry pointing at an existing record | accepted: avoid on the hosted app; Gmail search excluded, Drive on drive.file |
| 3 | Substrate decision per provider with the server's GA status | `decisions/substrate-google.md`, `decisions/substrate-microsoft.md`, `decisions/substrate-slack.md`; `substrate_decision` in each matrix | included actions must use a chosen substrate; non-GA MCP rows cannot be high confidence | accepted: Google sdk, Microsoft rest, Slack rest; Slack MCP deferred to 1.14 pending exact tool evidence |
| 4 | INT-2 connection-resolution contract signed off by lfx, langflow-base, Enterprise owners | `connection-contract.md` | sign-off coverage: every declared owner role has a row in the sign-off table below that lists the record | drafted 2026-09-01; 12 sections, owner questions in section 12 |
| 5 | Frontend surface list | `frontend-surfaces.md` | none | drafted 2026-09-01; 14 extend + 9 new, including the operator governance surface; MVP/defer split |
| 6 | Trigger/webhook track recorded as deferred | `triggers-deferred.md` | none | governing-plan findings folded in; provider transport and delivery discovery remains deferred |
| 7 | Re-issued estimate | `estimate.md` | none | re-issued 2026-09-01 and amended 2026-09-02: 48.75 engineer-weeks under the confirmed decisions |
| + | KB OAuth connector adoption decision (added by the release owner) | `decisions/kb-oauth-connector-adoption.md` | none | accepted: adopt in 1.13 (release owner overrode the gate's defer recommendation); +1.5 engineer-weeks |
| + | Palette naming next to Composio components (added by the release owner) | `decisions/palette-naming.md` | none | accepted: 'Product: Verb Object' names, new Microsoft 365 and Slack groups, Composio unchanged |
| + | Desktop OAuth registration ownership (added by the release owner, 2026-09-02) | `decisions/desktop-oauth-ownership.md` | none | accepted: Langflow-owned public clients on Desktop, customer-owned registrations remain the override; +0.25 engineer-weeks |

Gate close means: every row above is done, every record under `decisions/` is `Status: accepted` (the checker walks
them all, not only the ones a matrix references), every declared owner has completed both sign-off tables, and
`uv run python scripts/ci/check_capability_matrices.py --require-accepted` exits 0.

## Sign-off

Acceptance rule: `Status: accepted` on a record means the release owner accepted it; it is necessary but not
sufficient for gate close. Every other role a record names in its `Owners (sign-off roles):` line signs off in PR review
by approving and filling in its row below and in the record's own sign-off table. The checker
(`validate_sign_offs`) fails when a record names a role that has no row here, when that row does not list the
record, or when the record's own sign-off table is missing a declared role. In `--require-accepted` mode it also
fails blank or invalid Name, Date, and PR cells. Role placeholders remain until the release owner assigns names.

| Role | Signs off on | Name | Date | PR |
|---|---|---|---|---|
| lfx owner | `connection-contract.md`, `decisions/substrate-google.md`, `decisions/substrate-microsoft.md`, `decisions/substrate-slack.md`, `decisions/kb-oauth-connector-adoption.md` | | | |
| langflow-base owner | `connection-contract.md`, `decisions/substrate-google.md`, `decisions/substrate-microsoft.md`, `decisions/substrate-slack.md`, `decisions/google-restricted-scopes.md`, `decisions/kb-oauth-connector-adoption.md`, `decisions/desktop-oauth-ownership.md` | | | |
| Enterprise owner | `connection-contract.md`, `decisions/substrate-google.md`, `decisions/substrate-microsoft.md`, `decisions/substrate-slack.md`, `decisions/google-restricted-scopes.md` | | | |
| frontend owner | `connection-contract.md` (section 12.d), `frontend-surfaces.md`, `decisions/palette-naming.md` | | | |
| hosted-app owner | `decisions/google-restricted-scopes.md`, `decisions/substrate-google.md`, `decisions/substrate-microsoft.md`, `decisions/substrate-slack.md`, `decisions/desktop-oauth-ownership.md`, hosted and desktop rows of every matrix | | | |
| product owner | `decisions/palette-naming.md` | | | |
| platform owner | `triggers-deferred.md` | | | |
| release owner | every record in this directory, all matrices, `estimate.md`, gate close | Eric Hare | 2026-09-01 | #14906 |

## Running the checker

```bash
uv run python scripts/ci/check_capability_matrices.py
```

```bash
uv run python scripts/ci/check_capability_matrices.py --require-accepted
```

```bash
uv run pytest scripts/ci/test_capability_matrices.py
```

The checker validates every matrix against `schema/capability_matrix.schema.json` (Draft 2020-12 through
`jsonschema`, which the `CI Scripts Tests` workflow installs and the workspace environment already carries) before
applying the gate rules a schema cannot express, and runs on any change under this directory. Besides the matrices it
validates sign-off coverage: every `Owners (sign-off roles):` line under this directory must be
mirrored by the sign-off table above and by the record's own table.

## Directory map

```text
README.md                          this file
schema/capability_matrix.schema.json   JSON Schema for one provider matrix; its enums are asserted equal to the checker's
matrices/<provider>.json           one capability matrix per wave-1 provider
decisions/TEMPLATE.md              decision-record template; the checker parses the Status line and requires a "## Decision" heading
decisions/substrate-*.md           official MCP vs SDK/REST per provider
decisions/google-restricted-scopes.md   CASA-or-avoid for the Langflow-owned hosted Google app, one subsection per restricted scope
decisions/kb-oauth-connector-adoption.md   (Phase 6)
decisions/palette-naming.md        (Phase 6)
decisions/desktop-oauth-ownership.md   Desktop registrations: Langflow-owned public clients by default, customer-owned override (2026-09-02)
connection-contract.md             (Phase 5) INT-2 design for sign-off
frontend-surfaces.md               (Phase 7)
triggers-deferred.md               deferred track with re-open trigger
estimate.md                        (Phase 8)
```

## Matrix field glossary

Every claim-bearing value carries a `source` id that resolves in the matrix's top-level `sources` registry, and every
source carries the URL, a title, a kind, and the `verified_on` date it was last read. Verification for this gate is
documentation-only: no live tenants were exercised. Provider documentation remains authoritative for availability,
auth, and policy. A dated authenticated `mcp_tools_list` capture is authoritative for the exact tool identifiers and
schemas it enumerates and must be paired with provider documentation before an MCP substrate is selected.

Top level: `provider`, `display_name`, `bundle` (extension id, bundle name, distribution), `wave`,
`max_included_actions` (at most 8), `verified_on`, `oauth_app_owner_by_context` (who owns the OAuth registration in
each of `hosted`, `self_managed`, `desktop`, `headless`), `oauth_client_type_by_context` (`confidential`, `public`,
or externally provisioned per context), `substrate_decision` (`chosen` substrates and the decision record),
`restricted_scope_decisions` (one entry per restricted scope any included or deferred action carries), `sources`,
`verification_programs` (external verification or licensing programs an action depends on), `actions`.

Per action:

| Field | Meaning |
|---|---|
| `action_id` | Stable Langflow-owned id, `<provider>.<product>.<verb>`; becomes the manifest capability id in INT-3 |
| `component_class` | Proposed `*Component` class name; bare names must stay unique across bundles |
| `decision` | `include` (ships in wave 1), `exclude` (will not ship), `defer` (undecided or later wave) |
| `rationale`, `confidence`, `open_questions` | Why; how sure; what must be verified. `low` confidence requires open questions |
| `schema` | Proposed inputs and outputs, with the provider API page they map to. Required for included actions |
| `auth_mode` | How credentials are obtained: authorization code, client credentials, device code, service account, domain-wide delegation, bot install, API key |
| `identity` | Who executes: `user_delegated` (connected user), `bot` (app identity), `service` (service account or application permission) |
| `scopes[]` | Each with `classification`, the provider's own term in `provider_classification`, and a source. On included actions each scope also carries a `role`: `required` (always requested; becomes the manifest's `required_scopes`), `optional`, or `alternative`. Conditional roles become manifest `conditional_scopes` and carry a structured `condition` (`input_present` or `input_truthy`) that must name a declared action input. At least one scope is required |
| `consent` | `user`, `admin`, or `both`; with notes and a source. Required for included actions |
| `reach` | Effective resource and tenant reach. Required for included actions |
| `deployment_contexts` | Map of context to callback mechanism: `server_redirect`, `loopback_redirect`, `device_code`, `app_install_redirect`, `manual_token`, `none`. A context that is absent is unsupported |
| `refresh`, `revocation` | Token lifetime and revocation behavior with sources. Required for included actions |
| `substrate`, `substrate_ga_status` | `sdk`, `rest`, or `mcp`, and the provider server's maturity |
| `rate_limit` | Summary with a service-specific source and its own confidence. Required for included actions |
| `verification_dependencies` | Ids from `verification_programs` this action depends on |

### Scope classification mapping

The `classification` enum is Google's vocabulary applied to every provider so the exit criterion "every scope is
classified as non-sensitive, sensitive, or restricted" is checkable uniformly. The provider's own term is kept in
`provider_classification` so the mapping is auditable.

| Provider | `non_sensitive` | `sensitive` | `restricted` |
|---|---|---|---|
| Google | Google's non-sensitive list (for example `drive.file`) | Google's sensitive list (Calendar scopes, `gmail.send`, to verify) | Google's restricted list (most Gmail scopes, `drive.readonly`, to verify); triggers CASA for the requesting app |
| Microsoft Graph | Delegated permission without admin consent | Delegated permission that requires admin consent | Permission that needs Microsoft protected-API approval (for example application-permission Teams message reads) |
| Slack | Default scopes | Content-reading scopes (`search:read`, `*:history`, `canvases:read`) | `admin.*` and Discovery API scopes |

### Reference row shape

The shape below is illustrative; the authoritative rows live in `matrices/`. Values marked `...` are filled from a
cited source in Phase 1 or 2.

```json
{
  "action_id": "google.gmail.send",
  "display_name": "Gmail: Send Email",
  "component_class": "GmailSendComponent",
  "decision": "include",
  "rationale": "...",
  "confidence": "high",
  "schema": { "inputs": [ { "name": "to", "type": "list[str]", "required": true } ], "outputs": [ { "name": "message", "type": "Data" } ], "source": "gmail-messages-send" },
  "auth_mode": "oauth2_authorization_code",
  "identity": "user_delegated",
  "scopes": [ { "scope": "https://www.googleapis.com/auth/gmail.send", "classification": "sensitive", "provider_classification": "...", "source": "gmail-scopes", "role": "required" } ],
  "consent": "user",
  "consent_source": "...",
  "reach": { "resource": "...", "tenant": "...", "source": "..." },
  "deployment_contexts": { "hosted": "server_redirect", "self_managed": "server_redirect", "desktop": "loopback_redirect", "headless": "manual_token" },
  "refresh": { "behavior": "...", "source": "..." },
  "revocation": { "behavior": "...", "source": "..." },
  "substrate": "sdk",
  "substrate_ga_status": "ga",
  "substrate_source": "...",
  "rate_limit": { "summary": "...", "source": "...", "confidence": "high" },
  "verification_dependencies": ["google-oauth-app-verification"]
}
```

## Phases

| Phase | Deliverables | Needs a decision from the release owner |
|---|---|---|
| 0 | this scaffold, checker, seed rows | no |
| 1 | `matrices/google.json` fully sourced (done 2026-09-01) | no |
| 2 | `matrices/microsoft.json`, `matrices/slack.json` fully sourced (done 2026-09-01) | no |
| 3 | substrate decisions to `proposed` (drafted 2026-09-01) | yes: confirm Google sdk, Microsoft rest, Slack rest for 1.13 |
| 4 | `google-restricted-scopes.md` (drafted 2026-09-01, recommends avoid); rows flip on acceptance | yes: CASA or avoid |
| 5 | `connection-contract.md` (drafted 2026-09-01) | review by lfx, langflow-base, Enterprise owners |
| 6 | KB connector and palette naming decisions (drafted 2026-09-01) | yes |
| 7 | `frontend-surfaces.md` (drafted 2026-09-01) | no |
| 8 | `estimate.md` re-issued; all records `accepted`; owner sign-offs in PR review; `--require-accepted` turns green only after signatures are complete | estimate done; pending sign-offs |
