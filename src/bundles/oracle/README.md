# lfx-oracle

Oracle Database components (Doc Loader, Autonomous Database Loader,
Embeddings, Vector Store) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-oracle
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `Oracle` group.

## Develop

```bash
cd src/bundles/oracle
pip install -e .
lfx extension validate src/lfx_oracle
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.oracledb.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
