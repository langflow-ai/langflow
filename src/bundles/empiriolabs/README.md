# lfx-empiriolabs

EmpirioLabs as a standalone Langflow Extension Bundle.

Ships two components for [EmpirioLabs](https://empiriolabs.ai):

- **EmpirioLabs** — generates text using EmpirioLabs language models. EmpirioLabs
  exposes an OpenAI-compatible API (`https://api.empiriolabs.ai/v1`), so the
  component reuses `langchain_openai.ChatOpenAI` and can output either a
  **Model Response** (`Message`) or a **Language Model** (`LanguageModel`) for
  downstream components such as Agents.
- **EmpirioLabs Image Generation** — generates an image from a text prompt via
  the EmpirioLabs OpenAI-compatible Images endpoint
  (`POST /v1/images/generations`).

Both components fetch the live model list from the EmpirioLabs `/v1/models`
endpoint over `requests`, falling back to a bundled model list. This mirrors the
existing OpenAI-compatible provider bundles (`novita`, `cometapi`).

## Install

```bash
pip install lfx-empiriolabs
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components will
appear in the palette under the `EmpirioLabs` group.

You will need an EmpirioLabs API key (<https://empiriolabs.ai>) to run the
components. By default the components read it from the `EMPIRIOLABS_API_KEY`
environment variable.

## Develop

```bash
cd src/bundles/empiriolabs
pip install -e .
lfx extension validate src/lfx_empiriolabs
```

## Migration

Saved flows referencing the legacy class names or the old import paths under
`lfx.components.empiriolabs.*` are rewritten to the new namespaced IDs
`ext:empiriolabs:EmpirioLabsModelComponent@official` and
`ext:empiriolabs:EmpirioLabsImageGenerationComponent@official` by the migration
table in `src/lfx/src/lfx/extension/migration/migration_table.json`.
