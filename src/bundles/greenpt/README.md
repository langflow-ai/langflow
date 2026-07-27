# lfx-greenpt

Langflow extension for [GreenPT](https://greenpt.ai), a European AI provider
with an OpenAI-compatible API, optimized infrastructure, and data centers
powered by 100% renewable energy.

The extension adds:

- Live language-model and embedding-model discovery
- Chat models through GreenPT's OpenAI-compatible API
- Embeddings with `green-embedding`
- Document reranking with `green-rerank`
- Speech-to-text with GreenS Pro and GreenS

Install with:

```bash
uv pip install lfx-greenpt
```

Set `GREENPT_API_KEY`, then select GreenPT in Langflow's model provider dialog
or use the GreenPT Rerank and GreenPT Speech to Text components.
