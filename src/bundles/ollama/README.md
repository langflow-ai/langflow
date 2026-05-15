# lfx-ollama

Ollama component(s) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-ollama
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `ollama` group with
the namespaced IDs `ext:ollama:<Class>@official`.

## Develop

```bash
cd src/bundles/ollama
pip install -e .
lfx extension validate src/lfx_ollama
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.ollama.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
