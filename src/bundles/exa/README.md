# lfx-exa

[Exa](https://exa.ai/) web-search and contents tools as a standalone
Langflow Extension Bundle.

## What it ships

One component, registered under the `exa` bundle group:

- **Exa Search** (`ExaSearchToolkit`, canonical ID
  `ext:exa:ExaSearchToolkit@official`) — a toolkit exposing two tools for
  a Langflow **Agent** component or MCP client:
  - `search` — search the web with Exa (`auto` / `fast` / `instant` /
    `deep` search types, category, domain allow/deny lists, published-date
    range), returning token-efficient highlights by default.
  - `get_contents` — fetch highlights and/or full text for result IDs
    returned by `search`.

The component is built on the [`exa-py`](https://pypi.org/project/exa-py/)
SDK. It previously shipped inside the manifest-less `lfx-bundles`
metapackage on the deprecated `metaphor-python` client; the bundle name and
class name are unchanged, so saved flows load without migration changes.
The legacy `metaphor_api_key` field is still honored (hidden) — new flows
should use `exa_api_key`.

## Install

```bash
pip install lfx-exa
```

`pip install langflow` already includes it.

## Develop

The bundle is a uv workspace member of the Langflow monorepo:

```bash
uv sync
uv run pytest src/bundles/exa/tests -q
uv run lfx extension validate src/bundles/exa/src/lfx_exa
```

To iterate on the component with a live palette:

```bash
uv run lfx extension dev src/bundles/exa
```
