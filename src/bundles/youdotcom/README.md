# lfx-youdotcom

You.com web search, webpage extraction, and research components as a standalone Langflow Extension Bundle.

## Components

- `YouDotComSearchComponent` searches the web with optional highlights or full-page extraction.
- `YouDotComExtractComponent` extracts clean Markdown or HTML from webpages and PDFs.
- `YouDotComResearchComponent` returns a cited research answer, with optional combined and source-only outputs.

## Install

```bash
pip install lfx-youdotcom
```

The bundle is registered automatically via the `langflow.extensions` entry point. After installation, restart your Langflow server. The components appear in the palette under the `youdotcom` group with namespaced IDs `ext:youdotcom:<Class>@official`.

Set `YDC_API_KEY` or provide a You.com API key in each component. Get a key at https://you.com/platform/api-keys.

## Develop

```bash
cd src/bundles/youdotcom
uv pip install -e .
uv run lfx extension validate src/lfx_youdotcom
uv run pytest tests
```

The extension manifest is shipped at `src/lfx_youdotcom/extension.json` and points to `components/youdotcom`.
