# lfx-twelvelabs

Twelvelabs component(s) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-twelvelabs
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `twelvelabs` group with
the namespaced IDs `ext:twelvelabs:<Class>@official`.

## Develop

```bash
cd src/bundles/twelvelabs
pip install -e .
lfx extension validate src/lfx_twelvelabs
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.twelvelabs.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
