# lfx-desearch

Desearch web search, AI search and X search components as a standalone Langflow Extension Bundle.

The bundle ships three components that call the [Desearch](https://desearch.ai)
REST API directly with `httpx` and need only a user-supplied API key, so it
carries no vendor SDK dependency. See the
[Desearch docs](https://www.desearch.ai/docs) for the API details.

| Component | What it returns |
|-----------|-----------------|
| `DesearchWebSearchComponent` | Web results as a table with `title`, `link` and `snippet` columns. |
| `DesearchAISearchComponent` | An AI answer with links to its sources, plus a table of the sources. |
| `DesearchXSearchComponent` | X (Twitter) posts as a table with the post text, URL, author and counts. |

## Install

```bash
pip install lfx-desearch
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components
appear in the palette's **Bundles** section under **Desearch**.

## Configure

Set the **Desearch API Key** input to your own key from
[console.desearch.ai/api-keys](https://console.desearch.ai/api-keys). The
components are optional and do nothing until a key is supplied, so they change
nothing for anyone who does not use them.

- **Desearch Web Search**: query, plus an optional result offset for paging.
- **Desearch AI Search**: prompt, plus optional sources (web, twitter, reddit,
  hackernews, arxiv, wikipedia; default web and twitter) and date range.
- **Desearch X Search**: query, plus optional number of posts (1-100), sort
  (Top or Latest), user, language and start and end dates.

In tool mode, the components expose the tools `desearch_web_search`,
`desearch_ai_search` and `desearch_x_search`.

## Develop

```bash
cd src/bundles/desearch
pip install -e .
lfx extension validate src/lfx_desearch
```

## Manifest

The extension manifest is shipped at `src/lfx_desearch/extension.json` and
points at the bundle at `components/desearch`. The components register under
the canonical namespaced IDs `ext:desearch:DesearchWebSearchComponent@official`,
`ext:desearch:DesearchAISearchComponent@official` and
`ext:desearch:DesearchXSearchComponent@official`.
