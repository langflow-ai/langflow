# Substrate decision: Slack

Status: draft
Decision ID: substrate-slack
Applies to: matrices/slack.json, all actions; identity split user vs bot
Owners (sign-off roles): lfx owner, langflow-base owner, Enterprise owner, hosted-app owner, release owner
Last verified: 2026-09-01

## Context

Slack's official MCP server at mcp.slack.com is GA but issues user tokens only; bot tokens are excluded. The Slack Web API is GA for both identities. This record decides whether wave-1 Slack runs mixed (MCP for user-identity actions, Web API for bot actions) or Web API throughout, and how Desktop's PKCE rule (no bot scopes on desktop redirects) constrains the action set. Blocks INT-9 and INT-12.

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
