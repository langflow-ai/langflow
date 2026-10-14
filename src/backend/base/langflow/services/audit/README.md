# Represented audit identity

The Control Plane service verifies the caller's bearer token and derives its
issuer and subject. It calls Langflow with its own service API key and sends
these identity fields automatically. Public callers do not construct audit
metadata. Langflow still authorizes the authenticated service account.

Configure the Serving Plane before upgrading the Control Plane:

```bash
LANGFLOW_AUDIT_ENABLED=true
LANGFLOW_AUDIT_TRUSTED_API_KEY_IDS=<control-plane-api-key-record-uuid>
```

The allowlist contains database API-key **record IDs**, not API-key secrets or
account IDs. An empty list trusts no credential. Environment-backed keys have
no record ID and cannot assert represented identity. During rotation, allow
both record IDs, switch the Control Plane credential, then revoke the old key
and remove its ID from the allowlist.

The internal HTTP fields are fixed:

- `Langflow-Audit-Represented-Issuer`
- `Langflow-Audit-Represented-Subject`

Each value is `v1.` followed by unpadded base64url of the exact UTF-8 identity.
The issuer limit is 2048 Unicode characters. The subject limit is 512. No
normalization, case folding, or UUID conversion applies. Both fields must be
present exactly once or both absent. Empty values, control characters, invalid
UTF-8, noncanonical encoding, and oversized values produce HTTP 400 with
`X-Langflow-Error-Code: INVALID_AUDIT_CONTEXT`. A credential outside the exact
allowlist produces HTTP 403 with `REPRESENTED_IDENTITY_NOT_ALLOWED`. Validation
runs after authentication and before the mutation, even when auditing is off.
Use TLS for the service connection. The original bearer token is not forwarded.

Audit rows retain the authenticated account and credential in `user_id`,
`actor_type`, and `actor_id`. `acting_issuer` and `acting_subject` describe the
authenticated actor's own issuer-qualified identity when known. Control-plane
API-key calls have no such pair and leave these fields null. The asserted end-user identity is stored in
`represented_issuer` and `represented_subject`. Success and failure events use
the same validated request context. This metadata grants no permissions.

The migration adds the represented columns, pair constraint, and index without
changing acting columns or history. Existing rows retain null represented
identity. Neither pair is inferred from the other. Resource-specific and
combined audit responses expose both independent pairs. Acting and represented
filters apply to their respective columns and can be combined to select an
actor acting for a particular end user. Cursors are bound to the distinct filters.

The endpoint audit-wiring change is required for replacement-operation PUT
events. This identity transport does not create additional mutation events or
change receipt replay. Client correlation IDs are outside this change.
