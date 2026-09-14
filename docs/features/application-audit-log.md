# Application Audit Log

Langflow records one append-only event for each audited operation on a Flow or a
Project: who attempted it, which resource, when, how it ended, and a bounded,
safe description of what the operation wrote. An event describes an operation;
it is never a copy of resource state.

Contract: *IBM-Langflow: Audit Log Data & API Contracts* (2026-09-11). The
Control Plane consumes Project events to build its Deployment audit feed; Flow
events serve the Authoring Plane.

Off by default (`LANGFLOW_AUDIT_ENABLED=false`).

## Ubiquitous language

| Term | Meaning |
|---|---|
| Event | One row in `audit_events`. Never updated; deleted only by retention. |
| Event type | `authz` (was it permitted) or `action` (what the operation did). |
| Result | `allow`/`deny` for `authz`; `succeeded`/`failed` for `action`. |
| Action | The permission checked, such as `project:write`. |
| Operation | The mutation shape attempted: `create`, `replace`, `patch`, `delete`. |
| Account | `user_id`: the Langflow account the request executes under. |
| Actor | `actor_type`/`actor_id`: the credential that authenticated the request. |
| Acting identity | `acting_issuer`/`acting_subject`: the end user a trusted Control Plane acts for. |
| Details | Resource-owned, versioned JSON validated before it is stored. |

## Table: `audit_events`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `resource_type` | VARCHAR(64) NOT NULL | `project` or `flow` |
| `resource_id` | UUID NOT NULL | No foreign key; events outlive the resource |
| `resource_name` | VARCHAR(255) NULL | Event-time name, bounded to 255 characters |
| `user_id` | UUID NULL | No foreign key |
| `actor_type` | VARCHAR(32) NOT NULL | `user`, `api_key`, `service`, `system`, `unknown` |
| `actor_id` | UUID NULL | User id or API-key record id; no foreign key |
| `acting_issuer` | VARCHAR(2048) NULL | Set together with `acting_subject` |
| `acting_subject` | VARCHAR(512) NULL | Not assumed to be a UUID |
| `action` | VARCHAR(128) NOT NULL | Application-validated |
| `operation` | VARCHAR(64) NOT NULL | Application-validated |
| `event_type` | VARCHAR(16) NOT NULL | |
| `result` | VARCHAR(16) NOT NULL | |
| `error_code` | VARCHAR(64) NULL | Required for `deny`/`failed`, null otherwise |
| `timestamp` | TIMESTAMPTZ NOT NULL | App-server UTC when the event is staged |
| `request_id` | UUID NOT NULL | Server-generated per HTTP request; indexed, not unique |
| `details` | JSON NOT NULL | See [Details contract](#details-contract) |

Database checks cover only the closed vocabularies: the `event_type`/`result`
pairing and the acting pair being both null or both set. Action, operation and
error code evolve, so they are validated in the application and adding a value
never needs a migration.

Indexes: `(resource_type, resource_id, timestamp, id)`, `(resource_type,
timestamp, id)`, `(user_id, timestamp)`, `(actor_type, actor_id, timestamp)`,
`(acting_issuer, acting_subject, timestamp)`, `(request_id)`.

Migration `df1410b1eefa` — `Phase: EXPAND`, additive, reversible.

## Details contract

Every `details` object starts with `schema_version`. Unknown keys are rejected,
never persisted. Committed changes appear only on `succeeded` events; attempted
shape appears only on `failed` and `deny` events, so an attempt can never read
as a change.

**Project, schema 1**

- `description` — the value the operation wrote, stored complete. Absent means
  not written; `null` means written as null. No previous value is stored.
- `flows` — `before_count`, `after_count`, `updated_count` (exact), `changes`
  (at most 100 `{id, name, change}` entries ordered by change type then id,
  `change` in `added`/`removed`/`updated`), `truncated`. Classification is by
  Flow identity only; no content comparison.
- `attempted_fields`, `requested_flow_count` — failed or denied only.

**Flow, schema 1**

- `written_fields` — Flow attribute names the operation wrote.
- `project` — `{before_id, after_id}` when Project membership changed.
- `attempted_fields` — failed or denied only.

Field-name lists are unique, sorted, capped at 16, and must look like field
names, so a value cannot pass as one. Never stored: Flow descriptions, graphs,
nodes, edges, component settings, prompts, variables, secrets, request or
response bodies, exception text, payload hashes.

Error codes: `PERMISSION_DENIED`, `PROJECT_NOT_FOUND`, `PROJECT_NAME_CONFLICT`,
`FLOW_NOT_FOUND`, `FLOW_ID_CONFLICT`, `FLOW_NAME_CONFLICT`, `INVALID_CONTENT`,
`CONSTRAINT_VIOLATION`, `SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`, `UNKNOWN`.

## Helpers (`langflow.services.audit`)

| Helper | Behavior |
|---|---|
| `resolve_audit_actor(user_id)` | Derives account and credential from the request's authentication context. A caller cannot supply them. |
| `build_audit_event(draft)` | Validates a draft against the contract; raises `AuditContractError`. |
| `stage_audit_event(session, draft)` | Writes a committed operation's event in the mutation's transaction, flushed right after the mutation's own write, so a refused event fails the request and rolls the mutation back before any response. No-op when disabled or without a database. |
| `record_audit_event_after_rollback(draft)` | Writes a failure or denial in its own transaction, at most 4 concurrently, within 5 seconds. A storage failure is logged as an error and never raised into the already failing caller. |
| `list_audit_events(session, filters, limit, cursor, visibility)` | Filters (OR within a field, AND across), orders by `(timestamp DESC, id DESC)`, keyset pagination, cursor bound to its filters, no total. |
| `purge_expired_audit_events(session, retention_days)` | Deletes by age only. |

`AuditRequestContextMiddleware` gives every HTTP request its own
`request_id`, so the authorization and action events of one request share it.

## Invariants

1. A succeeded event and its mutation commit or roll back together.
2. A failed or denied event is written only after the mutation's transaction is gone.
3. An event violating the contract is refused before any database write.
4. Deleting a resource, user, or API key never deletes its events.
5. A traversal returns each event at most once, newest first; later inserts do not appear midway.
6. With `lfx serve` (no database), nothing is written and nothing raises.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `LANGFLOW_AUDIT_ENABLED` | `false` | Turns event production on. When on, production is always durable. |
| `LANGFLOW_AUDIT_RETENTION_DAYS` | `90` | Startup sweep plus a scheduled sweep on the `AUTHZ_AUDIT_CLEANUP_INTERVAL` cadence; `0` keeps everything. |

## Out of scope

- Atomic Project create/replace endpoints, inbound `request_id` propagation, and
  accepting an acting identity from the configured Control Plane service identity.
  The columns exist; nothing sets the acting pair yet.
- Flow run events, field-level content differences, version storage.
- Retiring `authz_audit_log`.

## Platform compatibility

No filesystem, subprocess, or path access. SQLite and PostgreSQL share one
schema; timestamps are normalized to UTC on read because SQLite returns them
without a timezone. Multiple replicas append without coordination; the
retention sweep runs per process and is idempotent. Python 3.10 compatible
(`asyncio.wait_for`, not `asyncio.timeout`).
