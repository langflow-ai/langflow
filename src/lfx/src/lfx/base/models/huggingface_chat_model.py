"""Local HuggingFace chat model adapter (llama-cpp-python backend).

We deliberately avoid the ``transformers`` + ``torch`` stack here. On macOS
arm64 + Python 3.12, importing torch inside a forked uvicorn worker causes
hard SIGSEGV crashes that no Python-level catch can recover from. Instead
we run quantized GGUF models through ``llama-cpp-python``, which:

- has no torch dependency (pure C/C++ backend with a thin Python binding);
- is fork-safe;
- is fast on CPU thanks to quantization (Q4_K_M etc.);
- ships in the existing ``langflow-base[llama-cpp]`` extra.

The catalog now stores GGUF repo ids; ``download_model`` pulls a single
``.gguf`` file via ``hf_hub_download`` and the adapter points
``ChatLlamaCpp`` at the resulting path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Disable huggingface_hub's accelerated/multi-threaded download backends
# *before* the library is imported anywhere in this process. xet and
# hf_transfer both spawn worker threads/processes that have triggered
# SIGSEGV inside forked uvicorn workers on macOS arm64. The plain
# single-threaded HTTP path is more than fast enough for ~270MB GGUFs.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

# Default bundled model. Q4_K_M-quantized SmolLM2-360M (~270MB), fast on CPU.
DEFAULT_HUGGINGFACE_MODEL = "bartowski/SmolLM2-360M-Instruct-GGUF"
DEFAULT_GGUF_FILENAME = "SmolLM2-360M-Instruct-Q4_K_M.gguf"

# Per-repo override of which GGUF file to fetch. Anything not listed here
# falls back to the ``*-Q4_K_M.gguf`` heuristic in ``_pick_gguf_filename``.
GGUF_FILENAME_BY_REPO: dict[str, str] = {
    DEFAULT_HUGGINGFACE_MODEL: DEFAULT_GGUF_FILENAME,
}

# Where huggingface_hub stores downloaded files.
HF_CACHE_DIR = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def _set_hf_token(api_key: str | None) -> None:
    """Forward an HF token to the env vars huggingface_hub looks at."""
    if api_key:
        os.environ.setdefault("HUGGINGFACEHUB_API_TOKEN", api_key)
        os.environ.setdefault("HF_TOKEN", api_key)


def _pick_gguf_filename(repo_id: str) -> str:
    """Pick a sensible default GGUF file when the catalog hasn't pinned one.

    Prefers Q4_K_M (good quality/size tradeoff). Callers can override by
    extending ``GGUF_FILENAME_BY_REPO``.
    """
    if repo_id in GGUF_FILENAME_BY_REPO:
        return GGUF_FILENAME_BY_REPO[repo_id]
    # Heuristic: <model-name>-Q4_K_M.gguf (works for bartowski-style repos).
    short = repo_id.split("/")[-1].removesuffix("-GGUF").removesuffix("-gguf")
    return f"{short}-Q4_K_M.gguf"


# In-process cache: building a Llama model is expensive (mmap + warmup),
# so reuse the same instance across calls for a given (path, settings).
_LLAMA_CACHE: dict[tuple, Any] = {}


def _get_or_build_chat_llamacpp(model_path: str, *, temperature: float | None, max_tokens: int | None) -> Any:
    cache_key = (model_path, temperature, max_tokens)
    if cache_key in _LLAMA_CACHE:
        return _LLAMA_CACHE[cache_key]

    try:
        from langchain_community.chat_models.llamacpp import ChatLlamaCpp
    except ImportError as exc:
        msg = (
            "Local HuggingFace inference uses the llama-cpp-python backend. "
            "Install it with: uv pip install 'langflow-base[llama-cpp]' langchain-community."
        )
        raise ImportError(msg) from exc

    kwargs: dict[str, Any] = {
        "model_path": model_path,
        "n_ctx": 2048,
        "n_threads": max(1, (os.cpu_count() or 2) - 1),
        "n_gpu_layers": 0,  # CPU-only by default; metal/cuda is opt-in via env tuning
        "verbose": False,
    }
    if temperature is not None:
        kwargs["temperature"] = float(temperature)
    if max_tokens is not None:
        kwargs["max_tokens"] = int(max_tokens)

    llm = ChatLlamaCpp(**kwargs)
    _LLAMA_CACHE[cache_key] = llm
    return llm


def build_local_chat_huggingface(
    model_id: str,
    *,
    api_key: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Any:
    """Construct a chat model backed by a local llama-cpp-python instance.

    Downloads the GGUF file if missing, then loads (or reuses) a cached
    ``ChatLlamaCpp`` pointed at the local path.
    """
    _set_hf_token(api_key)
    filename = _pick_gguf_filename(model_id)
    model_path = _ensure_gguf_cached(model_id, filename, api_key=api_key)
    return _get_or_build_chat_llamacpp(str(model_path), temperature=temperature, max_tokens=max_tokens)


def _ensure_gguf_cached(repo_id: str, filename: str, *, api_key: str | None) -> Path:
    """Download a single GGUF file from HF Hub if it isn't already cached.

    Tries an in-process ``hf_hub_download`` first. If that crashes or
    fails, retries the same call inside an isolated subprocess so a hard
    crash (SIGSEGV from xet/torch transitive imports) cannot take down
    the parent uvicorn worker.
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        msg = (
            "Downloading HuggingFace models requires the 'huggingface_hub' package. "
            "Install it with: uv pip install 'huggingface-hub[inference]'."
        )
        raise ImportError(msg) from exc

    _set_hf_token(api_key)
    try:
        path = hf_hub_download(repo_id=repo_id, filename=filename)
        return Path(path)
    except Exception as exc:  # noqa: BLE001
        from lfx.log.logger import logger

        logger.warning(
            "In-process hf_hub_download for %s failed (%s); retrying in subprocess.",
            repo_id,
            exc,
        )
        return _download_via_subprocess(repo_id, filename, api_key=api_key)


def _download_via_subprocess(repo_id: str, filename: str, *, api_key: str | None) -> Path:
    """Run ``hf_hub_download`` in a separate Python process.

    A subprocess can't crash the parent uvicorn worker. We capture stdout
    (the cached path) and forward stderr only on failure.
    """
    import subprocess
    import sys

    script = (
        "import os\n"
        "os.environ.setdefault('HF_HUB_DISABLE_XET', '1')\n"
        "os.environ.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '0')\n"
        "from huggingface_hub import hf_hub_download\n"
        f"print(hf_hub_download(repo_id={repo_id!r}, filename={filename!r}))\n"
    )
    env = os.environ.copy()
    env.setdefault("HF_HUB_DISABLE_XET", "1")
    env.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    if api_key:
        env["HUGGINGFACEHUB_API_TOKEN"] = api_key
        env["HF_TOKEN"] = api_key

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    if result.returncode != 0:
        msg = (
            f"Subprocess hf_hub_download failed for {repo_id} (exit {result.returncode}): "
            f"{result.stderr.strip() or 'no stderr captured'}"
        )
        raise RuntimeError(msg)
    out = result.stdout.strip().splitlines()
    if not out:
        msg = f"Subprocess hf_hub_download returned no path for {repo_id}"
        raise RuntimeError(msg)
    return Path(out[-1])


class ChatHuggingFace:
    """Factory shim that the unified registry instantiates.

    The unified ``get_llm`` calls ``ChatHuggingFace(model=..., api_key=...,
    temperature=..., max_tokens=..., streaming=...)``. We translate that
    into a llama-cpp-backed ``ChatLlamaCpp`` and return it from ``__new__``
    so callers receive a real ``BaseChatModel``.
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
        # llama-cpp's chat path streams natively but BaseChatModel handles
        # the streaming flag at a higher level; we don't need to forward it.
        del streaming, kwargs
        if not model:
            msg = "A 'model' (HuggingFace GGUF repo id) is required for the local HuggingFace provider."
            raise ValueError(msg)
        return build_local_chat_huggingface(
            model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def list_installed_models() -> list[str]:
    """Return repo ids that have at least one GGUF file in the local Hub cache."""
    if not HF_CACHE_DIR.exists():
        return []
    installed: list[str] = []
    for entry in HF_CACHE_DIR.iterdir():
        if not entry.is_dir() or not entry.name.startswith("models--"):
            continue
        # Only count repos that actually contain a .gguf file we can load.
        snapshots = entry / "snapshots"
        if snapshots.exists() and any(snapshots.rglob("*.gguf")):
            parts = entry.name[len("models--") :].split("--")
            if len(parts) >= 2:  # noqa: PLR2004
                installed.append("/".join(parts))
    installed.sort()
    return installed


def download_model(model_id: str, *, api_key: str | None = None) -> Path:
    """Eagerly download a GGUF file for ``model_id`` into the local cache.

    Returns the path to the cached ``.gguf`` file. Single-file download
    via ``hf_hub_download`` — no parallel fetcher, no torch import, safe
    on macOS arm64.
    """
    filename = _pick_gguf_filename(model_id)
    return _ensure_gguf_cached(model_id, filename, api_key=api_key)
