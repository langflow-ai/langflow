# lfx-notion

Notion component(s) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-notion
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `notion` group with
the namespaced IDs `ext:notion:<Class>@official`.

## Develop

```bash
cd src/bundles/notion
pip install -e .
lfx extension validate src/lfx_notion
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.notion.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
