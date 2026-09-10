# <Decision title>

Status: draft
Decision ID: <substrate-google | google-restricted-scopes | kb-oauth-connector-adoption | palette-naming | ...>
Applies to: <matrix file(s) and the action_ids or scopes this governs>
Owners (sign-off roles): <lfx owner>, <langflow-base owner>, <Enterprise owner>, <frontend owner>, <product owner>
Last verified: YYYY-MM-DD

<!--
Status is parsed by scripts/ci/check_capability_matrices.py and must be one of
draft | proposed | accepted | superseded. `--require-accepted` (gate close) fails on anything but accepted.
The "## Decision" heading is also required by the checker, and so is sign-off coverage: every role named on the
Owners line must have a row in the "## Sign-off" table below and in the README sign-off table, which must list this
file. `Status: accepted` records the release owner's decision; the other roles sign off in PR review.
-->

## Context

Why this decision is on the critical path and which INT tickets block on it.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | | | | |

Every fact used in Options or Decision appears here. Reuse the matrix `sources` ids in parentheses where one exists.

## Options

### Option A: <name>

Pros, cons, and what it costs (engineer-weeks, calendar time, recurring obligations).

### Option B: <name>

## Decision

One paragraph, imperative. For restricted-scope records, one `### <scope>` subsection per scope, each ending in
`Decision: avoid | accept_with_casa | accept_exempt | defer` (must match `restricted_scope_decisions` in the matrix).

## Consequences

Matrix rows that flip include/exclude/defer; contract or frontend surfaces affected; estimate delta.

## Re-open trigger

Concrete observable events (for example "Google Workspace MCP reaches GA", "Work IQ MCP drops the Copilot license
requirement", "mcp.slack.com documents bot-token support", "Google reclassifies gmail.send"). Include a re-verify-by date.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
| frontend owner | | | |
| product owner | | | |
