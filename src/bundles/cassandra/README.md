# lfx-cassandra

Cassandra component(s) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-cassandra
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `cassandra` group with
the namespaced IDs `ext:cassandra:<Class>@official`.

## Develop

```bash
cd src/bundles/cassandra
pip install -e .
lfx extension validate src/lfx_cassandra
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.cassandra.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
