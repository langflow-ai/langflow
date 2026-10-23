# lfx-geekflare

Geekflare web search, page scraping, and website diagnostics components as a standalone Langflow Extension Bundle.

The bundle ships three components that call the [Geekflare API](https://geekflare.com) directly with `httpx`. They need only a user-supplied API key, so the bundle carries no vendor SDK dependency. See the [Geekflare API docs](https://docs.geekflare.com) for API details.

| Component | What it does | Tool name |
| --- | --- | --- |
| `GeekflareSearchComponent` | Web, news, or image search returned as a table. Turn on **Google SERP** for the organic results of the full Google results page, by country or city. | `geekflare_search` |
| `GeekflareScrapeComponent` | Page content as Markdown, text, or HTML, with optional `product` or `contact` templates for structured data. | `geekflare_scrape` |
| `GeekflareWebsiteCheckComponent` | One website check: site status, DNS records, TLS scan, redirect chain, broken links, load time, or Lighthouse. | `geekflare_website_check` |

## Install

```bash
pip install lfx-geekflare
```

The bundle is registered automatically via the `langflow.extensions` entry-point. After install, restart your Langflow server; the components will appear in the palette's **Bundles** section under **Geekflare**.

## Configure

Set the **Geekflare API Key** input to your own key from [dash.geekflare.com](https://dash.geekflare.com) (a free tier is available). The components do nothing until a key is supplied, so they change nothing for anyone who does not use them. URLs can be full URLs or bare domains such as `example.com`. API errors are returned as a row or `Data` object with an `error` field instead of raising.

## Develop

```bash
cd src/bundles/geekflare
pip install -e .
lfx extension validate src/lfx_geekflare
```
