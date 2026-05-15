# lfx-mem0

Mem0 component(s) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-mem0
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `mem0` group with
the namespaced IDs `ext:mem0:<Class>@official`.

## Develop

```bash
cd src/bundles/mem0
pip install -e .
lfx extension validate src/lfx_mem0
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.mem0.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
