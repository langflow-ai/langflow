# Google restricted scopes on the Langflow-owned hosted app: CASA or avoid

Status: draft
Decision ID: google-restricted-scopes
Applies to: matrices/google.json, every scope classified restricted
Owners (sign-off roles): lfx owner, langflow-base owner, Enterprise owner, hosted-app owner, release owner
Last verified: 2026-09-01

## Context

Hosted Langflow ships in 1.13 with a Langflow-owned Google OAuth application. Google requires a CASA (Cloud Application Security Assessment) for any app requesting restricted scopes, with an annual recertification. Wave-1 candidates Gmail search (gmail.readonly) and Drive fetch beyond drive.file (drive.readonly) carry restricted scopes. This record decides, per restricted scope, whether the hosted app accepts CASA or wave 1 avoids the scope. Blocks INT-10 and the hosted rows of the auth matrix.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | To be filled in the phase that owns this record. | | | |

## Options

### Option A: to be drafted

### Option B: to be drafted

## Decision

Not yet taken. This record is a Phase 0 stub so the matrices can reference it; the checker's
`--require-accepted` mode will fail until it is accepted.

## Consequences

To be drafted.

## Re-open trigger

To be drafted.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
