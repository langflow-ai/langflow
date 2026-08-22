# lfx-adanos

[Adanos](https://adanos.org/) market sentiment data as a standalone Langflow Extension Bundle.

## What it ships

The **Adanos Market Sentiment** component retrieves read-only sentiment data for:

- individual stocks from Reddit, X / FinTwit, financial news, or Polymarket;
- individual crypto assets from Reddit;
- trending stocks or crypto assets; and
- aggregate stock or crypto market sentiment.

Results are returned as Langflow `Data` and can be passed to agents, prompts, or other data-processing components. The API key is sent only in the `X-API-Key` request header.

Create an API key at [adanos.org/register](https://adanos.org/register) and see the [Adanos API documentation](https://api.adanos.org/docs) for endpoint and plan details.

## Install

```bash
pip install lfx-adanos
```

`pip install langflow` already includes it.

## Develop

```bash
uv sync
uv run pytest src/bundles/adanos/tests -q
uv run lfx extension validate src/bundles/adanos/src/lfx_adanos
```
