# lfx-crawlerdata

CrawlerData Google Search (SERP) component as a standalone Langflow Extension Bundle.

The bundle ships a single component, `CrawlerDataSearchComponent`, which runs a
Google search through the [CrawlerData API](https://crawlerdata.com) and returns
the organic results as a table (`title`, `link`, `snippet`, `position`), plus Google's
AI Overview as the first row (its text followed by the pages it cites) when Google shows one. It calls the CrawlerData jobs endpoint directly with
`httpx` and needs only a user-supplied API key, so it carries no vendor SDK
dependency. See the [CrawlerData API docs](https://crawlerdata.com/apis/google-search-api)
for the API details.

## Install

```bash
pip install lfx-crawlerdata
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`CrawlerDataSearchComponent` will appear in the palette's **Bundles** section
under **CrawlerData**.

## Configure

Set the **CrawlerData API Key** input to your own key from
[app.crawlerdata.com](https://app.crawlerdata.com). The component is optional and
does nothing until a key is supplied, so it changes nothing for anyone who does
not use it. Country, language, device (desktop or mobile), location (city-level),
max results (1-100), page and **Include AI Overview** are optional advanced inputs.

Each search uses 1 CrawlerData credit; failed requests are not charged.

In tool mode, the component exposes a single tool named `crawlerdata_search`.

## Develop

```bash
cd src/bundles/crawlerdata
pip install -e .
lfx extension validate src/lfx_crawlerdata
```

## Manifest

The extension manifest is shipped at `src/lfx_crawlerdata/extension.json` and
points at the bundle at `components/crawlerdata`. The component registers under
the canonical namespaced ID `ext:crawlerdata:CrawlerDataSearchComponent@official`.
