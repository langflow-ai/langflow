# Knowledge-base OAuth connectors: adopt the connection contract in 1.13 or defer

Status: accepted
Decision ID: kb-oauth-connector-adoption
Applies to: src/lfx/src/lfx/base/knowledge_bases/ingestion_sources/ (OAuthConnectorBase and the Google Drive, OneDrive, SharePoint, Microsoft Graph sources); INT-2, INT-10, INT-11
Owners (sign-off roles): lfx owner, langflow-base owner, release owner
Last verified: 2026-09-01

## Context

The knowledge-base ingestion layer already has an OAuth base class and four cloud sources that were stubbed out
"until the first OAuth provider lands". The connection contract is that provider. This record decides whether the
KB sources adopt the contract in 1.13 or stay on their bring-your-own-refresh-token design until 1.14.

## Facts (with citations)

| # | Fact | Source | Verified on | Confidence |
|---|------|--------|-------------|------------|
| 1 | `OAuthConnectorBase(KBConnectorSource)` at `connector_base.py:140` resolves client id, client secret, and refresh token from three Langflow variables and exchanges the refresh token itself; access tokens are cached in-process with a 60 s margin | repo, `src/lfx/src/lfx/base/knowledge_bases/ingestion_sources/connector_base.py` | 2026-09-01 | high |
| 2 | The module docstring records the deferral: "No shared OAuth plumbing here: Phase 3B+ adds a dedicated OAuthConnectorBase subclass with token-refresh logic once the first OAuth provider lands" | same file, lines 1-25 | 2026-09-01 | high |
| 3 | `google_drive.py`, `onedrive.py`, `sharepoint.py`, `microsoft_graph.py` raise `NotImplementedError` and are not registered; `__init__.py` registers only `FILE_UPLOAD` and `FOLDER` | same directory | 2026-09-01 | high |
| 4 | KB ingestion runs as a background job whose executing identity is the job owner, so a connection used by ingestion is resolved non-interactively | `scripts/ci/execution_principal_matrix.json` (workflow_hitl_v2 and deployments families) and `connection-contract.md` section 4 | 2026-09-01 | medium |
| 5 | Drive and Graph ingestion need read scopes: Drive read beyond `drive.file` is restricted (CASA) and Graph `Files.Read.All` or `Sites.Read.All` are delegated without admin consent | `matrices/google.json`, `matrices/microsoft.json` | 2026-09-01 | high |

## Options

### Option A: Adopt in 1.13 (chosen)

`KBConnectorSource` accepts a `ConnectionRef`; `OAuthConnectorBase` becomes a thin adapter over
`Component.resolve_connection`; the four stubbed sources are re-registered against the Google and Microsoft
connections. Pros: one credential path for actions and ingestion; the stubs finally ship. Cons: ingestion is a
background job, so it needs the `allow_non_interactive` opt-in and the job-owner principal from INT-6 on day one;
Drive ingestion beyond app-scoped files needs a restricted scope the hosted app avoids
(`decisions/google-restricted-scopes.md`), so on hosted only OneDrive and SharePoint ingestion would actually work;
the KB UI has its own connector picker (`GET /api/v1/knowledge_bases/connectors`) that would need the connection
picker. Cost: roughly 1.5 engineer-weeks across INT-10 and INT-11 plus KB UI work not in any ticket.

### Option B: Defer to 1.14, keep the contract compatible (recommended by the gate, not chosen)

The KB sources stay disabled in 1.13; `OAuthConnectorBase` keeps bring-your-own refresh tokens for any customer who
already uses it. INT-2 keeps `KBConnectorSource` able to accept a `ConnectionRef` later without a breaking change
(the handle is a string field). Pros: no new scope on 1.13; the first consumer of the non-interactive opt-in is the
webhook and deployment path, which INT-6 already tests. Cons: the stubs stay stubs for one more release.
Cost: none in 1.13.

## Decision

Option A, chosen by the release owner on 2026-09-01 against the gate's recommendation. The knowledge-base OAuth
connectors adopt the connection contract in 1.13: `KBConnectorSource` accepts a connection handle, `OAuthConnectorBase`
becomes a thin adapter over `Component.resolve_connection`, and the Google Drive, OneDrive, SharePoint, and
Microsoft Graph sources are re-registered against the Google and Microsoft connections.

## Consequences

- INT-10 gains the Drive ingestion source and INT-11 gains the OneDrive, SharePoint, and Graph sources; the KB
  connector picker (`GET /api/v1/knowledge_bases/connectors`) gains the connection picker. Roughly 1.5 engineer-weeks
  across INT-10 and INT-11 plus KB UI work, now carried in `estimate.md`.
- KB ingestion runs as a background job, so it is the first day-one consumer of the per-connection
  `allow_non_interactive` opt-in and the job-owner principal from INT-6; INT-6 must land before the KB sources are
  enabled, and the ingestion source must surface the typed `connection-not-authorized` error when the opt-in is off.
- On hosted, Drive ingestion is limited to `drive.file` (files the app created or the user picked) under
  `decisions/google-restricted-scopes.md`; OneDrive and SharePoint ingestion are unaffected.
- The `source_config` shape for existing FILE_UPLOAD and FOLDER sources does not change; the connection handle is an
  additional field on the cloud sources only.

## Re-open trigger

- INT-4 and INT-6 land with the non-interactive opt-in tested, and a customer asks for Drive, OneDrive, or SharePoint
  ingestion, or
- the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| release owner | Eric Hare | 2026-09-01 | #14906 (confirmed in the planning session) |
