---
name: langflow-breaking-change-gate
description: Use when an edit could break existing user flows, API consumers, or installed databases — including renaming a component class, renaming/removing a component input or output `name=`, changing an output `method=`, removing/renaming a public export from `langflow.*` or `lfx.*`, changing or removing an API route path under `src/backend/base/langflow/api/v1/` or `v2/`, renaming/removing/retyping a field on an existing request or response schema, any new or modified alembic migration, or renaming an lfx CLI command/subcommand/required flag. Halts the change until the contributor explicitly confirms agreement with a maintainer has been reached.
---

# Breaking-Change Gate

Breaking changes in langflow are not advisory. They are agreed first, then made.

## Fires on

- **Component identifiers** — class name, input `name=`, output `name=`, output `method=`.
- **Public Python API** — anything exported from `langflow.*` or `lfx.*` top-level modules.
- **HTTP API** — routes under `src/backend/base/langflow/api/v1/` and `v2/`, request/response schemas.
- **Database** — any new or modified file under an `alembic/versions/` directory. Once a migration ships it has been run on user databases; it cannot be edited or removed.
- **lfx CLI** — command names, subcommand names, required flags.

## What to do

1. **Stop editing.** Do not apply the change yet.
2. **State the breaking change in plain terms** to the contributor:
   > "This would `<rename/remove/retype>` `<X>` to `<Y>`. That breaks `<existing user flows / API consumers / installed databases / CLI scripts>`."
3. **Ask explicitly:**
   > "Has this been agreed with a maintainer or decision-maker? Breaking changes require agreement first."
4. **Wait for a clear yes or no.** "I think so" is not yes.
   - **No or unsure** → do not make the change. Help the contributor draft the question for the maintainer: what's changing, why, what alternatives exist, what the migration story is.
   - **Yes** → proceed, and surface the migration path the maintainer agreed to (deprecation alias? schema versioning? migration script?). If none was discussed, the agreement wasn't deep enough — go back.

## Not breaking (do not fire)

- Adding a new component, input, output, route, schema field, CLI flag.
- Changing internals: function bodies, private helpers, anything not exported.
- Editing `description`, `display_name`, `icon`, docstrings.
- Bug fixes that restore the documented contract.

## Why this exists

Class names, input/output `name=`, route paths, schema fields, and migration files are identifiers and artifacts our users and their installations depend on. Renaming or reshaping them silently turns existing flows, scripts, integrations, and databases into bug reports. The cost of pausing to confirm agreement is small. The cost of an unannounced breaking change is large and falls on users.
