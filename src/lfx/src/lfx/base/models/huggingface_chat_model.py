"""Local HuggingFace chat model adapter.

Runs the model on the user's machine via ``langchain_huggingface``'s
``HuggingFacePipeline`` (which itself wraps ``transformers.pipeline``). The
adapter accepts the canonical kwargs the unified ``get_llm`` path produces
(``model``, ``api_key``, ``temperature``, ``max_tokens``, ``streaming``) and
translates them into the pipeline + ``ChatHuggingFace`` pair.

Models are downloaded lazily on first use to ``~/.cache/huggingface/hub`` and
reused for subsequent invocations. ``api_key`` is forwarded as the
``HUGGINGFACEHUB_API_TOKEN`` env var so gated/private models can be
downloaded; it is *not* required for public models.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Default bundled model: small (~720MB), instruct-tuned, fast on CPU.
DEFAULT_LOCAL_MODEL = "HuggingFaceTB/SmolLM2-360M-Instruct"

# Where transformers stores downloaded weights (mirrors HF default).
HF_CACHE_DIR = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def _set_hf_token(api_key: str | None) -> None:
    """Forward an HF token to the env vars huggingface_hub looks at."""
    if api_key:
        os.environ.setdefault("HUGGINGFACEHUB_API_TOKEN", api_key)
        os.environ.setdefault("HF_TOKEN", api_key)


def build_local_chat_huggingface(
    model_id: str,
    *,
    api_key: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Any:
    """Construct a ``ChatHuggingFace`` backed by a local transformers pipeline.

    Implementation notes:

    - We force ``device=-1`` (CPU) so the pipeline doesn't try to negotiate
      MPS / CUDA devices on first load. MPS in particular has triggered
      worker SIGSEGVs on macOS arm64 + Python 3.12 when torch is imported
      inside a forked uvicorn worker.
    - ``low_cpu_mem_usage=True`` reduces peak RAM during ``from_pretrained``
      by streaming weights into the model instead of materializing them
      twice. Helps on machines with limited RAM.
    - On macOS, set ``OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`` *before*
      starting the server if you still see SIGSEGV at first load — that's
      a torch+Objective-C fork-safety interaction, not specific to this
      adapter.
    """
    try:
        from langchain_huggingface import ChatHuggingFace as LCChatHuggingFace
        from langchain_huggingface import HuggingFacePipeline
    except ImportError as exc:
        msg = (
            "Local HuggingFace inference requires the 'langchain-huggingface' extra. "
            "Install it with: uv pip install 'langflow-base[langchain-huggingface]' "
            "(or 'pip install langchain-huggingface transformers torch')."
        )
        raise ImportError(msg) from exc

    _set_hf_token(api_key)

    pipeline_kwargs: dict[str, Any] = {}
    if max_tokens is not None:
        pipeline_kwargs["max_new_tokens"] = int(max_tokens)
    if temperature is not None:
        pipeline_kwargs["temperature"] = float(temperature)
        pipeline_kwargs["do_sample"] = True

    model_kwargs: dict[str, Any] = {
        # Stream weights into the model during from_pretrained instead of
        # double-buffering them — cuts peak RAM on the load path.
        "low_cpu_mem_usage": True,
    }

    llm = HuggingFacePipeline.from_model_id(
        model_id=model_id,
        task="text-generation",
        device=-1,
        model_kwargs=model_kwargs,
        pipeline_kwargs=pipeline_kwargs or None,
    )
    return LCChatHuggingFace(llm=llm, model_id=model_id)


class ChatHuggingFace:
    """Factory shim that the unified registry instantiates.

    The unified ``get_llm`` calls ``ChatHuggingFace(model=..., api_key=...,
    temperature=..., max_tokens=..., streaming=...)``. We translate that to a
    real ``langchain_huggingface.ChatHuggingFace`` wrapping a local pipeline,
    and return it from ``__new__`` so callers receive a proper
    ``BaseChatModel`` instance.
    """

    def __new__(
        cls,
        *,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        streaming: bool = False,
        **kwargs: Any,
    ):
        # streaming/kwargs accepted for unified-registry compatibility; the
        # local pipeline doesn't expose token-level streaming today.
        del streaming, kwargs
        if not model:
            msg = "A 'model' (HuggingFace repo id) is required for the local HuggingFace provider."
            raise ValueError(msg)
        return build_local_chat_huggingface(
            model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def list_installed_models() -> list[str]:
    """Return repo ids that are present in the local HF hub cache.

    Reads ``~/.cache/huggingface/hub`` directory entries of the form
    ``models--{org}--{name}``. Does not import transformers/torch.
    """
    if not HF_CACHE_DIR.exists():
        return []
    installed: list[str] = []
    for entry in HF_CACHE_DIR.iterdir():
        if not entry.is_dir() or not entry.name.startswith("models--"):
            continue
        parts = entry.name[len("models--") :].split("--")
        if len(parts) >= 2:  # noqa: PLR2004
            installed.append("/".join(parts))
    installed.sort()
    return installed


def download_model(model_id: str, *, api_key: str | None = None) -> Path:
    """Eagerly download model weights to the local HF cache.

    Uses ``huggingface_hub.snapshot_download`` which is light (no torch
    needed) and pulls only the files required for inference.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        msg = (
            "Downloading HuggingFace models requires the 'huggingface_hub' package. "
            "Install it with: uv pip install 'huggingface-hub[inference]'."
        )
        raise ImportError(msg) from exc

    _set_hf_token(api_key)
    path = snapshot_download(
        repo_id=model_id,
        # Skip large optional files that the runtime doesn't load.
        ignore_patterns=["*.bin.index.json.bak", "*.msgpack", "*.h5", "*.ot"],
    )
    return Path(path)
