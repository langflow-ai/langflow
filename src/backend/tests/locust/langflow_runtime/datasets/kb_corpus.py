"""On-demand KB corpus materialization for performance-suite tests and Locust runs.

Docs are not committed: call ``materialize_kb_corpus`` before use and
``cleanup_kb_corpus`` afterward (or use ``kb_corpus`` as a context manager).
Used by KB/ensemble cases in ``tests/locust/tests/integration/`` and by any
Locust profile that selects the KB dataset ids from ``registry``.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_DOC_PREFIX, DEFAULT_KB_QUERY

if TYPE_CHECKING:
    from collections.abc import Iterator

KB_DOC_COUNT = 3
KB_DOC_BYTES = 500 * 1024  # 500 KiB per document
KB_CHUNK_SIZE = 200


def known_token(index: int) -> str:
    return f"PERF_KB_TOKEN_{index}"


def render_kb_document(index: int, *, size_bytes: int = KB_DOC_BYTES) -> bytes:
    """Return a deterministic document body of exactly ``size_bytes`` bytes."""
    if index < 0:
        msg = f"document index must be >= 0 (got {index})"
        raise ValueError(msg)
    header = (
        f"{DEFAULT_KB_DOC_PREFIX} document={index}\nknown_token={known_token(index)}\nquery_anchor={DEFAULT_KB_QUERY}\n"
    ).encode("ascii")
    footer = f"\nend={index}\n".encode("ascii")
    pad_len = size_bytes - len(header) - len(footer)
    if pad_len < 0:
        msg = f"size_bytes={size_bytes} too small for KB document headers"
        raise ValueError(msg)
    unit = b"lorem "
    pad = (unit * ((pad_len // len(unit)) + 1))[:pad_len]
    body = header + pad + footer
    if len(body) != size_bytes:
        msg = f"rendered KB doc length {len(body)} != {size_bytes}"
        raise RuntimeError(msg)
    return body


def materialize_kb_corpus(
    root: Path,
    *,
    document_count: int = KB_DOC_COUNT,
    size_bytes: int = KB_DOC_BYTES,
) -> list[Path]:
    """Write ``doc_00.txt`` … under ``root`` and return their paths."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index in range(document_count):
        path = root / f"doc_{index:02d}.txt"
        path.write_bytes(render_kb_document(index, size_bytes=size_bytes))
        paths.append(path)
    return paths


def cleanup_kb_corpus(root: Path) -> None:
    """Remove generated ``doc_*.txt`` files under ``root`` (and ``root`` if empty)."""
    root = Path(root)
    if not root.exists():
        return
    for path in root.glob("doc_*.txt"):
        path.unlink(missing_ok=True)
    # Non-empty or not a directory — leave the rest alone.
    with suppress(OSError):
        root.rmdir()


@contextmanager
def kb_corpus(
    root: Path,
    *,
    document_count: int = KB_DOC_COUNT,
    size_bytes: int = KB_DOC_BYTES,
) -> Iterator[list[Path]]:
    """Materialize the corpus under ``root`` and always clean it up."""
    paths = materialize_kb_corpus(root, document_count=document_count, size_bytes=size_bytes)
    try:
        yield paths
    finally:
        cleanup_kb_corpus(root)
