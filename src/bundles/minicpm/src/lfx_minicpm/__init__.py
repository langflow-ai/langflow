"""lfx-minicpm: MiniCPM-OCR bundle.

This package is the distribution unit ``lfx-minicpm``. At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers ``MiniCPMOCRComponent`` under the namespaced ID
``ext:minicpm:MiniCPMOCRComponent@official``.

MiniCPM-OCR (https://github.com/OpenBMB/MiniCPM-OCR) is a 1.3B document OCR
model served through an OpenAI-compatible chat-completions endpoint
(vLLM/SGLang/llama.cpp/Ollama). The component renders PDF pages locally and
calls that endpoint, so the bundle carries no model SDK dependency.
"""

from lfx_minicpm.components.minicpm.minicpm_ocr import MiniCPMOCRComponent

__all__ = ["MiniCPMOCRComponent"]
