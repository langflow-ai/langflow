# Re-adding OSS / Enterprise Plugin Support

After the revert (PR #11878) was merged to main, use these steps to bring the feature back with a **migration that matches the models** so existing DBs and new installs both work.

## Why the original migration failed

- The migration created a **unique index** on `(sso_provider, sso_user_id)`.
- The model declared a **UniqueConstraint** on the same columns.
- Alembic treats index and constraint as different, so it reported a model/DB mismatch and startup failed for users who had already run the migration.

## Next steps (in order)

### 1. Branch from current main

```bash
git fetch origin main
git checkout -b feat/oss-enterprise-plugin-support-v2 origin/main
```

### 2. Re-apply the feature code

Re-introduce all non-migration changes from your original PR, for example:

- Plugin route loading (e.g. `plugin_routes.py`, wiring in `main.py` or `endpoints.py`).
- SSO (and any other) **models** under `langflow/services/database/models/`.
- Any API endpoints, tests, and config that belonged to the feature.

Do **not** re-add the old migration file `2ef4ca4016a3_add_sso_plugin_tables_...`. Use the new migration from step 3 instead.

### 3. Align the SSO model with the migration (critical)

In `SSOUserProfile`, the uniqueness on `(sso_provider, sso_user_id)` must be declared as a **unique index**, not a `UniqueConstraint`, so it matches what the migration creates and Alembic does not see a diff.

In `src/backend/base/langflow/services/database/models/auth/sso.py`:

```python
from sqlalchemy import Column, ForeignKey, Index  # not UniqueConstraint

class SSOUserProfile(SQLModel, table=True):
    __tablename__ = "sso_user_profile"
    # Use Index(unique=True) so model matches migration; avoids model/DB mismatch.
    __table_args__ = (Index("uq_sso_user_profile_provider_user", "sso_provider", "sso_user_id", unique=True),)
    # ... rest of fields unchanged
```

### 4. Add the new migration only

- Add **one** new migration file that creates the SSO tables (see the migration file added in this repo:  
  `src/backend/base/langflow/alembic/versions/b1c2d3e4f5a6_add_sso_plugin_tables_sso_user_profile_.py`).
- That migration:
  - Has `down_revision = "369268b9af8b"` (current head on main after the revert).
  - Creates `sso_config` and `sso_user_profile` only **if the table does not exist** (idempotent).
  - Creates the uniqueness on `(sso_provider, sso_user_id)` as a **unique index** (same name `uq_sso_user_profile_provider_user`), not a constraint.

So:

- **New installs:** Migration creates tables and index → model declares same index → no mismatch.
- **Existing users who still have the old SSO tables (from before the revert):** Tables already exist; migration skips creation; model declares the same index they already have → no mismatch.

### 5. Run and verify

- Run migrations: `alembic upgrade head` (or start the app so it runs migrations).
- Run backend tests, including SSO model tests.
- Optionally run the migration validator:  
  `python src/backend/base/langflow/alembic/migration_validator.py src/backend/base/langflow/alembic/versions/b1c2d3e4f5a6_add_sso_plugin_tables_sso_user_profile_.py`

### 6. Open the new PR

- Open a new PR with the re-applied feature + model fix + **only** the new migration (no old `2ef4ca4016a3`).
- Ensure CI (including migration validation) passes.

## Summary

| Item | Action |
|------|--------|
| Feature code | Re-apply from original PR (routes, models, API, tests). |
| SSO model | Use `Index(..., unique=True)` for `(sso_provider, sso_user_id)`. |
| Migration | Use the new migration that creates tables + **unique index** idempotently. |
| Old migration | Do not re-add `2ef4ca4016a3`. |

This keeps the migration and model in sync and avoids breaking existing or new databases.
