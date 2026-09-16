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
| `stage_audit_event(session, draft)` | Writes a committed operation's event in the mutation's transaction, flushed right after the mutation's own write, so a refused event fails the request and rolls the mutation back before any response. No-op, without a flush, when disabled, when the action is excluded, or without a database. |
| `record_audit_event_after_rollback(draft)` | Writes a failure or denial in its own transaction, at most 4 concurrently, within 5 seconds. A storage failure is logged as an error and never raised into the already failing caller. No-op, without opening a connection, when disabled or when the action is excluded. |
| `is_action_audited(action)` | False when `LANGFLOW_AUDIT_EXCLUDE_EVENTS` excludes the action. Both writers above check it, so no producer can bypass an exclusion. |
| `list_audit_events(session, filters, limit, cursor, visibility)` | Filters (OR within a field, AND across), orders by `(timestamp DESC, id DESC)`, keyset pagination, cursor bound to its filters, no total. |
| `purge_expired_audit_events(session, retention_days)` | Deletes by age only. |

`AuditRequestContextMiddleware` gives every HTTP request its own
`request_id`, so the authorization and action events of one request share it.

## Producers (existing write routes)

Each route below carries one `@audited_route` decorator. Succeeded events are
written where the mutation happens, right after its own write; failures and
denials are written by the decorator and the permission guards.

| Route | resource / action / operation | Succeeded `details` |
|---|---|---|
| `POST /flows/` | flow / `flow:create` / `create` | `written_fields`, `project.after_id` |
| `PATCH /flows/{id}` | flow / `flow:write` / `patch` | `written_fields`; `project` when moved |
| `PUT /flows/{id}` existing | flow / `flow:write` / `replace` | `written_fields`; `project` when moved |
| `PUT /flows/{id}` new id | flow / `flow:create` / `create` | as create |
| `DELETE /flows/{id}` | flow / `flow:delete` / `delete` | `project.before_id` |
| `POST /flows/batch/`, `POST /flows/upload/` | one flow event per Flow created or replaced | |
| `DELETE /flows/` | one `flow:delete` per Flow | |
| `POST /flows/{id}/versions/{v}/activate` | flow / `flow:write` / `patch` | `written_fields: ["data"]` |
| Any flow run (`simple_run_flow`, build driver) | flow / `flow:execute` / `run` | `run.trigger`, `run.duration_ms` |
| `POST /projects/` | project / `project:create` / `create` | `description` when supplied; `flows` (added) |
| `PATCH /projects/{id}` | project / `project:write` / `patch` | `description` only when written |
| `PUT /projects/{id}` existing | project / `project:write` / `patch` | same as PATCH (the route has PATCH semantics) |
| `PUT /projects/{id}` new id | project / `project:create` / `create` | as create |
| `DELETE /projects/{id}` | project / `project:delete` / `delete` | `flows` (removed); plus one `flow:delete` per Flow removed |
| `POST /projects/upload/` | project / `project:create` / `create` | `description`, `flows` (added); plus one `flow:create` per Flow |

`replace` for Projects (atomic complete-content replacement) arrives with the
atomic Project APIs; no existing route replaces a Project's contents.

**Flow runs** — every run records one `flow` / `flow:execute` / `run` event with
its outcome, whichever surface started it. Both run funnels are decorated, so
the API (`/run`, streaming), webhooks, the Playground build, MCP, OpenAI
Responses and the workflow API are all covered without per-route code.

| Field | Value |
|---|---|
| actor | who ran it: the user, or `api_key` with the key id |
| `result` / `error_code` | `succeeded`; or `failed` with `INVALID_CONTENT` (the request was wrong), `FLOW_NOT_FOUND`, `CONSTRAINT_VIOLATION`, `SERVICE_UNAVAILABLE`, or `FLOW_EXECUTION_FAILED` (a component failed, raised or not) |
| `details` | `{"schema_version": 1, "run": {"trigger": "<execution family>", "duration_ms": <int>}}` only |

Never stored for a run: inputs, outputs, tweaks, the request body, the result,
or the error text. A paused run (human input) records nothing until the resume
that completes it; a cancelled run records nothing. A refused `flow:execute`
records one `authz`/`deny` at the permission guard, so every run surface is
covered. A run writes nothing to the Flow, so its event has its own transaction.

The run event is written in the background, so it never delays or fails the
response. Busy databases (SQLite under a burst of runs) can refuse or time out a
write, so each event is retried with backoff (6 attempts, 30s each). Every
attempt inserts a fresh row with the same id, so an attempt that committed
but then timed out is not duplicated: the primary key rejects the retry.
Pending writes finish on shutdown. An event that never lands is logged with
`op=persist_run_event outcome=not_persisted`. A run that fails because the
database is locked records `failed` with `SERVICE_UNAVAILABLE`.

**Outcome rules**

- A request refused before authorization (unknown id, owner-scoped 404, malformed body) records nothing.
- A guard that refuses records one `authz`/`deny` with `PERMISSION_DENIED` and no action event. For Flow PATCH, DELETE and create the guard is the route dependency.
- Anything raised after authorization records one `action`/`failed` after the transaction rolled back, with a code derived from the error: a uniqueness message maps to `*_NAME_CONFLICT`, a duplicate id to `FLOW_ID_CONFLICT`, 400/422 to `INVALID_CONTENT`, a domain 403 or 423 to `CONSTRAINT_VIOLATION`, a generic 500 by its database cause (`OperationalError` to `SERVICE_UNAVAILABLE`, `IntegrityError` to `CONSTRAINT_VIOLATION`), else `INTERNAL_ERROR`.
- A failure after an explicit commit (the Memory Base teardown after a delete) is never recorded as failed.
- A failed attempt with no identity yet (a denied or failed create without an id) uses `resource_id = 00000000-0000-0000-0000-000000000000`.
- The failed or denied `resource_name` is the known name of an existing resource, otherwise the attempted name.

**Transaction ownership.** Project create, rename and auth reconciliation used to
commit the request transaction midway through MCP server registration, so a
create that failed afterwards left the Project behind. Those calls now join the
request transaction (`owns_transaction=False`). Project delete still commits MCP
cleanup first; that does not affect the audit, because the Project removal and
its event share the later transaction.

## Read API: `GET /api/v1/projects/audits`

A read-only, Project-specific view over `audit_events`. It never returns
Project or Flow content, and reading records no event.

**Query parameters** — `project_id`, `operation`*, `event_type`*, `result`*,
`user_id`, `actor_type`*, `actor_id`, `acting_subject`, `acting_issuer`
(requires `acting_subject`), `request_id`, `since` (inclusive RFC 3339),
`until` (exclusive, later than `since`), `cursor`, `limit` (1–200, default 50).
Parameters marked * are repeatable and ORed; different parameters are ANDed.

**400** for an unknown parameter, an empty value, a malformed UUID or timestamp
(an offset is required), an unsupported value, a repeated non-repeatable
parameter, an out-of-range limit, or a cursor used with different filters.

**Response**

```json
{
  "items": [
    {
      "id": "…", "timestamp": "2026-09-11T16:42:18.284123Z",
      "project_id": "…", "project_name": "support-automation",
      "action": "project:write", "operation": "patch",
      "event_type": "action", "result": "succeeded", "error_code": null,
      "request_id": "…",
      "actor": {"type": "user", "id": "…", "user_id": "…", "acting_issuer": null, "acting_subject": null},
      "details": {"schema_version": 1, "description": "…"}
    }
  ],
  "next_cursor": null
}
```

Nullable and always present: `project_name`, `error_code`, `actor.id`,
`actor.user_id`, `actor.acting_issuer`, `actor.acting_subject`, `next_cursor`.
No total and no page number. Ordered by `(timestamp DESC, id DESC)`; the
timestamp keeps microseconds so a client re-sorting a page agrees with the server.

**Access.** Requires the `project:audit_read` permission (`ProjectAction.AUDIT_READ`),
which a role can grant like any other `project:*` action.

| Caller | Without `project_id` | With `project_id` |
|---|---|---|
| Plugin with cross-user fetch | global `project:audit_read` | `project:audit_read` on that Project |
| No plugin, superuser | every Project event | that Project's events |
| No plugin, other users | events on Projects they own, and events they made | the same, narrowed to that Project |

A deleted Project's events stay readable by whoever acted on it, because
there is no longer an owner to derive visibility from.

## Invariants

1. A succeeded event and its mutation commit or roll back together.
2. A failed or denied event is written only after the mutation's transaction is gone.
3. An event violating the contract is refused before any database write.
4. Deleting a resource, user, or API key never deletes its events.
5. A traversal returns each event at most once, newest first; later inserts do not appear midway.
6. With `lfx serve` (no database), nothing is written and nothing raises.
7. A request that is not audited (auditing off, or a helper called outside an audited route such as startup or the assistant) writes nothing.
8. A run records at most one outcome, even when it starts nested runs, is retried, or streams.
9. An excluded action writes nothing for any outcome, and the operation behaves exactly as with auditing off.
10. An exclusion entry that matches no audited action excludes nothing and never stops startup.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `LANGFLOW_AUDIT_ENABLED` | `false` | Turns event production on. When on, production is always durable. |
| `LANGFLOW_AUDIT_RETENTION_DAYS` | `90` | Startup sweep plus a scheduled sweep on the `AUTHZ_AUDIT_CLEANUP_INTERVAL` cadence; `0` keeps everything. |
| `LANGFLOW_AUDIT_EXCLUDE_EVENTS` | empty | Comma-separated actions never recorded. See [Excluding actions](#excluding-actions). |

### Excluding actions

`LANGFLOW_AUDIT_EXCLUDE_EVENTS` names actions exactly as the `action` column
stores them, so a value copied from an event works as an entry.

| Entry | Excludes |
|---|---|
| `project:delete` | That one action |
| `flow:*` | Every action on that resource |
| `*:delete` | That action on every resource |

```bash
LANGFLOW_AUDIT_EXCLUDE_EVENTS=flow:execute,project:delete
```

- **Every outcome.** An excluded action records no `succeeded`, `failed` or
  `deny` event. To keep refusals while dropping routine writes, do not exclude
  the action.
- **Exact, per action.** Excluding `project:delete` keeps the `flow:delete`
  event of each Flow the deleted Project removed, and excluding `flow:*` keeps
  every Project event, including the Flow summary inside it.
- **Runs.** `flow:execute` is the highest-volume action. Excluding it skips the
  run event before any timing, name lookup or background write, on every run
  surface, and drops refused runs too.
- **Normalized.** Entries are trimmed and lowercased; empty and repeated
  entries are dropped.
- **Ignored, never guessed.** An entry that matches no audited action is ignored
  and excludes nothing: a misspelling such as `projects.delete`, an unknown
  resource or action, or a malformed entry. Startup logs one warning per ignored
  entry, with the correct spelling when there is an obvious one. `*:*` and `*`
  are ignored too: to record nothing, set `LANGFLOW_AUDIT_ENABLED=false`.
  Ignoring rather than refusing to start keeps a typo on the side of recording
  too much, and lets an older replica start with a value only a newer release
  understands.
- **Future events only.** Excluding an action deletes nothing already stored,
  and the read APIs are unchanged.
- **Read per event.** The value is compiled once per distinct setting, so a
  settings change applies to the next event without a restart.

## Out of scope

- Atomic Project create/replace endpoints, inbound `request_id` propagation, and
  accepting an acting identity from the configured Control Plane service identity.
  The columns exist; nothing sets the acting pair yet.
- Field-level content differences, version storage, run inputs and outputs.
- Retiring `authz_audit_log`.

## Platform compatibility

No filesystem, subprocess, or path access. SQLite and PostgreSQL share one
schema; timestamps are normalized to UTC on read because SQLite returns them
without a timezone. Multiple replicas append without coordination; the
retention sweep runs per process and is idempotent. Python 3.10 compatible
(`asyncio.wait_for`, not `asyncio.timeout`).
