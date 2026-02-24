"""Shared helpers for CAMB.AI Langflow components."""

from __future__ import annotations

import asyncio
import struct
import tempfile
from typing import Any


async def poll_task(client: Any, get_status_fn: Any, task_id: str, max_attempts: int = 60, interval: float = 2.0) -> Any:
    """Poll a CAMB.AI async task until completion."""
    for _ in range(max_attempts):
        status = await get_status_fn(task_id)
        if hasattr(status, "status"):
            val = status.status
            if val in ("completed", "SUCCESS", "complete"):
                return status
            if val in ("failed", "FAILED", "error", "ERROR", "TIMEOUT", "PAYMENT_REQUIRED"):
                reason = getattr(status, "exception_reason", "") or getattr(status, "error", "Unknown error")
                raise RuntimeError(f"CAMB.AI task failed: {val}. {reason}")
        await asyncio.sleep(interval)
    raise TimeoutError(f"CAMB.AI task {task_id} did not complete within {max_attempts * interval}s")


def detect_audio_format(data: bytes) -> str:
    """Detect audio format from raw bytes."""
    if not data:
        return "wav"
    if data[:4] == b"RIFF":
        return "wav"
    if data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
        return "mp3"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:4] == b"OggS":
        return "ogg"
    return "wav"


def add_wav_header(raw_data: bytes, sample_rate: int = 24000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Add a WAV header to raw PCM audio data."""
    data_size = len(raw_data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE", b"fmt ", 16, 1,
        channels, sample_rate, sample_rate * channels * bits_per_sample // 8,
        channels * bits_per_sample // 8, bits_per_sample, b"data", data_size,
    )
    return header + raw_data


def save_audio(data: bytes, extension: str = "wav") -> str:
    """Save audio data to a temporary file and return the file path."""
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as f:
        f.write(data)
        return f.name


def get_async_client(api_key: str, timeout: float = 60.0) -> Any:
    """Create an AsyncCambAI client."""
    try:
        from camb.client import AsyncCambAI
    except ImportError as e:
        raise ImportError("The 'camb' package is required. Install it with: pip install camb") from e
    return AsyncCambAI(api_key=api_key, timeout=timeout)
