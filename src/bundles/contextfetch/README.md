# lfx-contextfetch

ContextFetch web search and page contents components as a standalone Langflow Extension Bundle.

The bundle ships two components:

- `ContextFetchSearchComponent` searches the web through the
  [ContextFetch API](https://contextfetch.dev) and returns the results with
  page content as Markdown (pruned context, highlights or full text) as a table.
- `ContextFetchContentsComponent` fetches one or more pages by URL and returns
  each page as Markdown.

Both call the ContextFetch API directly with `httpx` and need only a
user-supplied API key, so the bundle carries no vendor SDK dependency. See the
[ContextFetch docs](https://contextfetch.dev/docs) for the API details.

## Install

```bash
pip install lfx-contextfetch
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components
appear in the palette's **Bundles** section under **ContextFetch**.

## Configure

Set the **ContextFetch API Key** input to your own key. The docs at
[contextfetch.dev/docs](https://contextfetch.dev/docs) explain how to get a
free key. The components are optional and do nothing until a key is supplied.

Search: max results (1-25), page content (Pruned Context, Highlights or Full
Text), include and exclude domains, and a published-after date.
Get Contents: URLs (up to 100) and an optional highlights query.

In tool mode, the components expose the tools `contextfetch_search` and
`contextfetch_get_contents`.

## Develop

```bash
cd src/bundles/contextfetch
pip install -e .
lfx extension validate src/lfx_contextfetch
```

## Manifest

The extension manifest is shipped at `src/lfx_contextfetch/extension.json` and
points at the bundle at `components/contextfetch`. The components register
under the canonical namespaced IDs
`ext:contextfetch:ContextFetchSearchComponent@official` and
`ext:contextfetch:ContextFetchContentsComponent@official`.
