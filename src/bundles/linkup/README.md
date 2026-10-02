# lfx-linkup

[Linkup](https://www.linkup.so) web-search and fetch components as a
standalone Langflow Extension Bundle.

## What it ships

Two components, registered under the `linkup` bundle group:

- **Linkup Search** (`LinkupSearchComponent`, canonical ID
  `ext:linkup:LinkupSearchComponent@official`) — search the web in real time
  with `fast` / `standard` / `deep` depth, optional domain allow/deny lists,
  a published-date range and a result cap. It has two outputs:
  - **Search Results** — a table of sources with `title`, `url` and
    `content` columns.
  - **Sourced Answer** — a natural-language answer followed by its sources.
- **Linkup Fetch** (`LinkupFetchComponent`, canonical ID
  `ext:linkup:LinkupFetchComponent@official`) — fetch a single URL and return
  its content as markdown, optionally rendering JavaScript first.

In tool mode, the components expose the tools `linkup_search`,
`linkup_sourced_answer` and `linkup_fetch`.

Both components are built on the official
[`linkup-sdk`](https://pypi.org/project/linkup-sdk/) client. See the
[Linkup docs](https://docs.linkup.so) for the API details.

## Install

```bash
pip install lfx-linkup
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components
appear in the palette's **Bundles** section under **Linkup**.

## Configure

Set the **Linkup API Key** input to your own key from
[app.linkup.so](https://app.linkup.so).

## Develop

The bundle is a uv workspace member of the Langflow monorepo:

```bash
uv sync
uv run pytest src/bundles/linkup/tests -q
uv run lfx extension validate src/bundles/linkup/src/lfx_linkup
```

To iterate on the components with a live palette:

```bash
uv run lfx extension dev src/bundles/linkup
```
