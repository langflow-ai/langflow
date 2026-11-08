---
title: Offline secret-key audit and rotation
---

`LANGFLOW_SECRET_KEY` protects stored credentials and signs local HS256 sessions.
Each Editor and Runtime has its own root. Deployment transfer never copies a
root key between instances. Keep the old root and a verified database backup
until the replacement has been activated and checked.

## Audit

`langflow secrets audit` reads every persisted encrypted value without changing
it. It reports counts plus table, column, and row IDs for failures and supported
legacy plaintext. It never reports variable names, secret values, or database
URLs. The exit status is nonzero if any encrypted value cannot be decrypted.

```sh
langflow secrets audit --key-env CURRENT_ROOT --database-url-env ROTATION_DATABASE_URL
```

Options name environment variables; their values contain the key and synchronous
SQLite or PostgreSQL connection URL. Supply secrets through your secret manager
or a protected environment, not command arguments or shell history.

## Rotate

1. Stop **all** web processes, background workers, and trigger listeners using the
   database. Keep them stopped until every process receives the new root.
2. Create and verify a database backup. Record its SHA-256 independently. Keep the
   old and new roots available outside the database. Apply the current schema
   migrations, including `secret_rotation`, before the offline operation.
3. Set the old and new roots in separate environment variables and run:

```sh
langflow secrets rotate \
  --database-url-env ROTATION_DATABASE_URL \
  --old-key-env OLD_ROOT --new-key-env NEW_ROOT \
  --writers-stopped \
  --backup-file /protected/backups/langflow.dump \
  --backup-sha256 "$VERIFIED_BACKUP_SHA256"
```

The command requires a nonempty backup file matching the supplied digest and
rejects the live SQLite file as its own backup. The digest proves artifact
identity; operators must also validate that their backup can be restored.
SQLite uses an immediate write transaction. PostgreSQL takes exclusive table
locks and refuses a conflicting lock. The operator's shutdown attestation is
required because locks do not keep old-key processes stopped after commit.

The shared inventory covers Store keys, credential variables, folder MCP auth,
API keys, deployment provider credentials, connection secrets and OAuth
verifiers (including expired rows), trigger signing and cleanup credentials,
MCP server env/header/argument secrets, encrypted job request overrides, and
HKDF SSO envelopes. Supported legacy plaintext is reported and preserved.
Malformed or undecryptable ciphertext aborts the operation.

All values are audited before writing, rewrapped with explicit-key cryptography,
and verified again with the new root. Any failure rolls back the database.
Only a fully verified commit creates a `secret_rotation` receipt. This receipt
records database completion, fingerprints, backup digest, and counts. It does
**not** mean external key configuration has been activated.

Update the deployment's root Secret or environment, restart every process, and
confirm a new audit succeeds. Local HS256 sessions must sign in again. External
RS256 trust and signing keys are separate and are not rotated by this command.
If activation fails after database commit, keep writers stopped. Retry activation
with the new root, or restore the verified database backup together with the old
root. Never restart the old root against a successfully rotated database.

For an operator-managed migration, add `--instance-uid <Langflow CR UID>` and
`--receipt-file /protected/receipt.json`. The file is created only after the
verified commit and contains schema version 1, that instance UID, domain-separated
fingerprints of both roots (`previous_key_fingerprint` and `key_fingerprint`), status
`completed`, and the database rotation UUID. For an already managed instance,
the old fingerprint must equal the operator's currently accepted root. The
operator records consumed rotation UUIDs and their transitions, so an older
receipt cannot be reused after a later rotation, even if a key is reused.
An administrator installs it as `receipt.json` in the migration receipt Secret.
The operator validates its binding before activating a migrated root.

Every receipt output uses the same 64-character hexadecimal HMAC-SHA-256
fingerprint: the HMAC key is the UTF-8 string
`langflow/secret-rotation/root-fingerprint/v1`, and the message is the root's
UTF-8 bytes. Operator integrations must use this computation when comparing
roots. Raw SHA-256 fingerprints are unsafe because they expose the Fernet key
derived from short roots.

## Enterprise integration

Install the matching Enterprise package before auditing or rotating. The host
loads its `langflow.secret_rotation` entry point. The participant adds SSO draft
and historical revision envelopes to the same transaction. Supply the same
runtime database and Redis settings as the stopped deployment. A mismatch with
the target database is refused.

Pending SSO callbacks and CLI login records are invalidated in their exact
instance namespaces. Testing SSO drafts return to draft so users can restart the
test. Redis invalidation is checked before database commit; any failure leaves
no success receipt. Invalidation cannot be rolled back, so users may need to
restart a pending login even when the database rotation fails. No unrelated
Redis namespace is cleared.

The compatibility script `scripts/migrate_secret_key.py` reuses the inventory
and crypto, retains its old/new key-file lifecycle, and refuses active jobs and
live OAuth callbacks. Its CLI now requires the same shutdown and backup proof
for mutations. Use the packaged command for durable receipts and operator
activation. A dry run remains read-only.
