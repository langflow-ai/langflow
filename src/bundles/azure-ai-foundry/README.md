# lfx-azure-ai-foundry

Azure AI Foundry as a first-class model provider for [Langflow](https://github.com/langflow-ai/langflow), packaged as a standalone Extension Bundle.

## What this bundle adds

- **Azure AI Foundry** provider in the Langflow model picker
- Pre-populated model catalog: `gpt-4o` (default), `gpt-4o-mini`, `gpt-4.1`, `o3-mini`, `Mistral-Large-3`
- Credential validation against the Azure AI Foundry OpenAI-compatible endpoint

## Configuration

Set these environment variables (or enter them in the Langflow UI):

| Variable | Description |
|---|---|
| `AZURE_AI_FOUNDRY_API_KEY` | API key from the Azure AI Foundry portal |
| `AZURE_AI_FOUNDRY_ENDPOINT` | OpenAI-compatible endpoint, e.g. `https://<resource>.services.ai.azure.com/openai/v1` |

## Installation

```bash
pip install lfx-azure-ai-foundry
```

Langflow detects the bundle automatically via the `langflow.extensions` entry-point — no manual registration needed.

## Requirements

- `lfx >= 1.11.0`
- `langchain-azure-ai >= 0.1.0`
