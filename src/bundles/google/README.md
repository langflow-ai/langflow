# lfx-google

Google and Gemini components as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-google
```

`pip install langflow` includes this bundle because Google Generative AI is a
supported model provider. The bundle is registered automatically through the
`langflow.extensions` entry point and appears under the `google` group with
canonical component IDs such as
`ext:google:GoogleGenerativeAIComponent@official`.

## Develop

```bash
uv sync
uv run pytest src/bundles/google/tests -q
uv run lfx extension validate src/bundles/google/src/lfx_google
```

The bundle graduated from the manifest-less `lfx-bundles[google]` provider in
Langflow 1.12. Its bundle and class names are unchanged, so existing saved
flows retain their canonical IDs.
