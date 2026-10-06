# lfx-atlascloud

Atlas Cloud as a standalone Langflow Extension Bundle.

Ships one component for [Atlas Cloud](https://atlascloud.ai):

- **Atlas Cloud** — generates text using Atlas Cloud language models. Atlas
  Cloud exposes an OpenAI-compatible API (`https://api.atlascloud.ai/v1`), so
  the component reuses `langchain_openai.ChatOpenAI` and can output either a
  **Model Response** (`Message`) or a **Language Model** (`LanguageModel`) for
  downstream components such as Agents.

The component fetches the live model list from the Atlas Cloud `/v1/models`
endpoint over `requests`, falling back to a bundled model list. This mirrors
the existing OpenAI-compatible provider bundles (`novita`, `cometapi`,
`empiriolabs`). Two differences worth knowing:

- Atlas Cloud serves `/v1/models` **without authentication**, so the model
  dropdown fills in before a key is entered. The key is still sent when one is
  present.
- One endpoint fronts chat, image and OCR models, and the catalog reports
  `output_modalities: ["text"]` for all of them, so the non-chat entries are
  filtered out by id rather than by that field.

## Install

```bash
pip install lfx-atlascloud
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the component will
appear in the palette under the `Atlas Cloud` group.

You will need an Atlas Cloud API key (<https://atlascloud.ai>) to run the
component. By default it reads it from the `ATLASCLOUD_API_KEY` environment
variable.

## Develop

```bash
cd src/bundles/atlascloud
pip install -e .
lfx extension validate src/lfx_atlascloud
```

## Migration

None. This bundle is new: its component never shipped in-tree under
`lfx.components.atlascloud.*`, so there are no legacy import paths for
`src/lfx/src/lfx/extension/migration/migration_table.json` to rewrite.
