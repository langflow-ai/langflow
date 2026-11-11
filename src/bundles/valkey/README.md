# lfx-valkey

Valkey component(s) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-valkey
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `valkey` group with
the namespaced IDs `ext:valkey:<Class>@official`.

The Valkey Vector Store requires Python 3.10 through 3.14 on Linux or macOS.
Its GLIDE driver has no Python 3.15 wheel, and the source build omits a required
generated protobuf module. The vector store reports this limitation before
calling the driver. Valkey Chat Memory remains available on Python 3.15.

## Develop

```bash
cd src/bundles/valkey
pip install -e .
lfx extension validate src/lfx_valkey
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.valkey.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
