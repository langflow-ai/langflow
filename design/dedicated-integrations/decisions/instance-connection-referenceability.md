# Instance-connection referenceability in 1.13

Status: accepted
Decision ID: instance-connection-referenceability
Applies to: `scripts/ci/execution_principal_matrix.json` (`connection_resolution` for every family); `Connection.ownership_mode = instance`; INT-6, INT-7
Owners (sign-off roles): langflow-base owner, Enterprise owner
Last verified: 2026-09-05

## Context

`connection-contract.md` sections 12.b.1 and 12.c.2 leave open which principals, flows or tenants may
reference an INSTANCE-owned connection. INT-6 stamps a principal at every entry point and is therefore the
first ticket whose code must answer the question: `_select_authorized_candidate` picks an instance row as
the fallback when the principal owns no row with that handle, and something has to decide whether that is
allowed.

The assessment for INT-6 assumed INT-7 (LE-2465) owned this. It does not: LE-2465 scopes an approved
provider set and per-action allow/block keys in the shared policy bundle, enforced at discovery and before
adapter invocation. Nothing in it says which principals may reference an instance credential. Without this
record, INT-6's implementation default silently becomes 1.13 product behavior.

## Facts (with citations)

| # | Fact | Source | Verified on | Confidence |
|---|------|--------|-------------|------------|
| 1 | The portable floor denies `anonymous_public` and `unknown` for every owner kind, and applies the owner-match and interactive/opt-in rules only to `owner_kind == "user"` — so an instance row resolves for any other principal | `src/lfx/src/lfx/services/connection/base.py` `authorize_principal` | 2026-09-05 | high |
| 2 | An owned row shadows the instance fallback, and a denial on the owned row does not fall through to the instance row (no silent identity switch) | `src/backend/base/langflow/services/connection/service.py` `_select_authorized_candidate` | 2026-09-05 | high |
| 3 | The `Connection` model has `allow_non_interactive` but no `referenceable` flag, so contract 12.b.1's "only when the instance connection is flagged referenceable" is not expressible without a new column and an alembic migration | `src/backend/base/langflow/services/database/models/connection/` | 2026-09-05 | high |
| 4 | LE-2465 (INT-7) governs approved providers and per-action keys, not principal referenceability | `jira/LE-2465.md` | 2026-09-05 | high |
| 5 | Creating an instance connection is already an administrative act; a non-admin cannot mint one | `src/backend/base/langflow/api/v1/connections.py` ownership-mode guard | 2026-09-05 | medium |

## Options

### Option A: Keep the floor, add a policy hook (chosen)

Any principal except `anonymous_public`/`unknown` may resolve an instance row. INT-6 adds
`DatabaseConnectionResolverService.authorize_instance_connection(request, row=...)`, a seam whose 1.13
implementation returns `None` (allow) and which an integration-policy service overrides to narrow. No new
column, no migration, no change to INT-4's API shape.

Cost: zero engineer-weeks now. Recurring obligation: every instance connection an operator provisions is
usable by every authenticated principal until a policy overrides the hook, which must be documented.

### Option B: Add a `referenceable` flag now

Matches contract 12.b.1 literally. Costs an alembic migration inside INT-6, a change to INT-4's
already-open connection API shape, and a default (`true` preserves today's behavior, `false` makes every
existing instance connection stop working) that has to be chosen without a policy engine to explain it.

## Decision

Ship Option A. In 1.13, an instance-owned connection resolves for any execution principal that is not
`anonymous_public` or `unknown`; anonymous and public execution is a hard deny with no override, matching
the LE-2464 ticket text ("public, A2A, and anonymous executions never resolve user connections") and the
`never` rule those families carry in the execution-principal matrix. Referenceability narrowing is
expressed through `authorize_instance_connection`, not through a stored flag; a `referenceable` column is
deferred until a policy owner asks for one.

## Consequences

- The matrix's `connection_resolution` values describe USER-owned rows. Instance rows follow this record,
  which is why no family carries an `instance_*` value.
- The anonymous rule is now enforced twice: the portable floor denies it, and the matrix checker rejects any
  family that pairs `dependency_principal: anonymous_public` with anything but `connection_resolution: never`.
- Enterprise gets a single override point rather than a schema it must migrate onto.
- `docs/docs/Develop/connection-oauth.mdx` documents the operator-visible half: provisioning an instance
  connection makes it available to every authenticated principal in the deployment.
- Estimate delta: none.

## Re-open trigger

Any of: an Enterprise policy ticket asks for per-tenant or per-flow instance referenceability; a customer
provisions an instance connection whose provider account must not be reachable by every user in the
deployment; INT-7's policy bundle grows a principal dimension. Re-verify by 2026-12-01.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| langflow-base owner | | | |
| Enterprise owner | | | |
