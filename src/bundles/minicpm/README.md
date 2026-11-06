# lfx-minicpm

MiniCPM-OCR as a standalone Langflow Extension Bundle.

Ships the **MiniCPM OCR** component, which extracts text from images and
scanned PDFs with [MiniCPM-OCR](https://github.com/OpenBMB/MiniCPM-OCR), a 1.3B
open OCR model. It calls a self-hosted OpenAI-compatible chat-completions
endpoint (vLLM, SGLang, llama.cpp or Ollama) directly via `httpx` and renders
PDF pages locally with `pypdfium2`, so it does **not** require the
`minicpm-ocr` Python SDK or its Paddle layout dependencies.

## Install

```bash
pip install lfx-minicpm
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the component appears
in the palette under the `minicpm` group.

## Run the model

```bash
vllm serve openbmb/MiniCPM-OCR-1.0 --port 8000
```

Point the component's **Base URL** at `http://127.0.0.1:8000` (do not append
`/v1`; the component does that itself). Ollama and llama.cpp serve the same
OpenAI-compatible shape; SGLang and LMDeploy use the `openai`-compatible mode.
Set an **API Key** only when the server requires one.

The component sends the page image before the prompt and includes the
`mm_processor_kwargs` slice arguments that MiniCPM-OCR's own client uses. If an
endpoint rejects that field with HTTP 400 or 422, the request is retried once
without it.

## Output

Each input file produces one `Data` object:

- `text` — the recognized Markdown/text, pages joined with blank lines;
- `data.page_count` — number of OCR'd pages;
- `data.model`, `data.ocr_engine` — endpoint model name and `minicpm-ocr`.

## Develop

```bash
cd src/bundles/minicpm
pip install -e .
pytest tests
lfx extension validate src/lfx_minicpm
```

## Limitations

- The component performs page-level OCR, so table structure and reading order
  depend on the served model. Use a document-parsing component (Docling,
  MinerU, PaddleOCR) when structured layout recovery is required.
- A scanned PDF is rendered at 200 DPI; very large files take time and one
  request per page.
