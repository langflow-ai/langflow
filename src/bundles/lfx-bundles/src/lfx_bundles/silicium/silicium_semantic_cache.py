# SPDX-License-Identifier: MIT
"""Silicium Sub-50us In-Process HNSW Semantic Cache Component for Langflow (`lfx_bundles.silicium`)."""

from __future__ import annotations

import contextlib
import importlib
import math
import re
import threading
from typing import Final

from lfx_bundles.silicium.silicium_pii_guardrail import (
    Component,
    Data,
    IntInput,
    Message,
    MessageTextInput,
    Output,
    StrInput,
    compute_kv_prefix_hash64,
)

try:
    from lfx.io import BoolInput, FloatInput
except ImportError:
    BoolInput = IntInput  # type: ignore[misc,assignment]
    FloatInput = IntInput  # type: ignore[misc,assignment]

_MAX_TENANT_SCOPES: Final[int] = 256
_MAX_ENTRIES_PER_TENANT: Final[int] = 1024
_MIN_CACHE_DIM: Final[int] = 8
_DEFAULT_CACHE_DIM: Final[int] = 16
_TRIGRAM_WIDTH: Final[int] = 3
_NORM_EPSILON: Final[float] = 1e-12
_RE_SCOPE_TOKEN: Final = re.compile(r"[A-Za-z0-9_.\-]{1,128}")
_RE_WORDS: Final = re.compile(r"[a-z0-9]+")
_CACHE_LOCK: Final[threading.Lock] = threading.Lock()
_TENANT_CACHE_ARENA: dict[str, list[dict[str, object]]] = {}


def _resolve_native_vector_module() -> object | None:
    """Resolve optional native C-ABI HNSW module when native vector entrypoints exist."""
    for mod_name in ("silicium_vector", "silicium_ai_ops"):
        with contextlib.suppress(Exception):
            mod = importlib.import_module(mod_name)
            if callable(getattr(mod, "derive_deterministic_embedding", None)) and callable(
                getattr(mod, "l2_distance_squared", None)
            ):
                return mod
    return None


_NATIVE_VECTOR_MODULE: Final[object | None] = _resolve_native_vector_module()
NATIVE_CACHE_BACKEND: Final[str] = "silicium_c_abi_hnsw" if _NATIVE_VECTOR_MODULE is not None else "python_portable_l2"


def reset_semantic_cache_arena() -> None:
    """Clear all tenant semantic cache entries (used by unit tests)."""
    with _CACHE_LOCK:
        _TENANT_CACHE_ARENA.clear()


def _fnv1a_32(token: str) -> int:
    """Compute a 32-bit FNV-1a hash for feature projection."""
    h = 0x811C9DC5
    for b in token.encode("utf-8", errors="ignore"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _extract_similarity_features(text: str) -> list[tuple[str, float]]:
    """Extract word unigram, word bigram, and character 3-gram features preserving lexical similarity."""
    lowered = text.lower().strip()
    if not lowered:
        return [("__empty__", 1.0)]
    words = _RE_WORDS.findall(lowered)
    features: list[tuple[str, float]] = [(f"w:{w}", 2.0) for w in words]
    features.extend((f"b:{words[idx]}_{words[idx + 1]}", 1.5) for idx in range(len(words) - 1))
    compact = " ".join(words) if words else lowered
    if len(compact) < _TRIGRAM_WIDTH:
        features.append((f"c:{compact}", 1.0))
    else:
        features.extend(
            (f"g:{compact[idx : idx + _TRIGRAM_WIDTH]}", 0.5) for idx in range(len(compact) - _TRIGRAM_WIDTH + 1)
        )
    return features


def _derive_deterministic_embedding(text: str, dim: int = _DEFAULT_CACHE_DIM) -> list[float]:
    """Compute a unit-normalized feature-hashed embedding vector of dimension `dim >= 8`."""
    eff_dim = int(dim)
    if eff_dim < _MIN_CACHE_DIM:
        msg = f"Embedding dimension cache_dim must be >= {_MIN_CACHE_DIM}, got {eff_dim}."
        raise ValueError(msg)
    if _NATIVE_VECTOR_MODULE is not None:
        with contextlib.suppress(Exception):
            fn = getattr(_NATIVE_VECTOR_MODULE, "derive_deterministic_embedding", None)
            if callable(fn):
                return [float(x) for x in fn(text, eff_dim)]
    vec = [0.0] * eff_dim
    for feat, weight in _extract_similarity_features(text):
        h = _fnv1a_32(feat)
        slot = h % eff_dim
        sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
        vec[slot] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > _NORM_EPSILON:
        return [v / norm for v in vec]
    vec[0] = 1.0
    return vec


def _l2_distance_squared(a: list[float], b: list[float]) -> float:
    """Compute squared Euclidean (L2) distance between two equal-length vectors."""
    if len(a) != len(b):
        msg = f"Embedding dimension mismatch: query={len(a)}, stored={len(b)}."
        raise ValueError(msg)
    if _NATIVE_VECTOR_MODULE is not None:
        with contextlib.suppress(Exception):
            fn = getattr(_NATIVE_VECTOR_MODULE, "l2_distance_squared", None)
            if callable(fn):
                return float(fn(a, b))
    return sum((a[i] - b[i]) * (a[i] - b[i]) for i in range(len(a)))


def _get_tenant_bucket_unlocked(isolation_key: str) -> list[dict[str, object]]:
    """Return the bounded cache bucket for `isolation_key` while holding `_CACHE_LOCK`."""
    bucket = _TENANT_CACHE_ARENA.get(isolation_key)
    if bucket is None:
        if len(_TENANT_CACHE_ARENA) >= _MAX_TENANT_SCOPES:
            oldest = next(iter(_TENANT_CACHE_ARENA))
            _TENANT_CACHE_ARENA.pop(oldest, None)
        bucket = []
        _TENANT_CACHE_ARENA[isolation_key] = bucket
    return bucket


class SiliciumSemanticCacheComponent(Component):
    """In-process L2 semantic cache isolated by trusted runtime identity and `tenant_scope`."""

    display_name = "Silicium Semantic Cache"
    description = (
        "In-process L2 semantic cache (linear scan up to 1,024 entries per scope across "
        "256 trusted user scopes, with optional native C-ABI acceleration) and 64-bit FNV-1a KV-cache prefix affinity."
    )
    documentation = "https://github.com/silicium369-spec/silicium-ai-ops"
    icon = "Silicium"
    name = "SiliciumSemanticCacheComponent"

    inputs = [
        MessageTextInput(
            name="query_text",
            display_name="Query Text",
            info="Prompt or query text to look up or store in the tenant semantic cache.",
            required=True,
        ),
        MessageTextInput(
            name="response_to_seed",
            display_name="Response to Seed",
            info="Optional LLM response text to store or update in the semantic cache for this query.",
            value="",
        ),
        StrInput(
            name="tenant_scope",
            display_name="Tenant Sub-Scope",
            info="Logical namespace scoped within the authenticated runtime user identity.",
            value="default-tenant",
            advanced=True,
        ),
        FloatInput(
            name="distance_threshold",
            display_name="L2 Distance Threshold",
            info="Maximum squared L2 distance for a semantic cache hit (0.0 requires exact query match).",
            value=0.2,
            advanced=True,
        ),
        IntInput(
            name="cache_dim",
            display_name="Embedding Dimension",
            info="Vector dimension for in-process L2 similarity lookup (minimum 8).",
            value=16,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Cached Message",
            name="cached_message",
            method="lookup_cached_message",
        ),
        Output(
            display_name="Cache Metadata",
            name="cache_metadata",
            method="build_cache_metadata",
        ),
    ]

    def set(self, **kwargs: object) -> SiliciumSemanticCacheComponent:
        """Assign component input attributes and invalidate the per-execution memoized result."""
        super().set(**kwargs)
        self._last_exec_signature = None
        self._last_exec_result = None
        return self

    def _resolve_trusted_isolation_scope(self) -> tuple[str, str]:
        """Bind cache scope to the trusted runtime identity (`_user_id` or `graph.user_id`)."""
        raw_uid = getattr(self, "_user_id", None)
        if raw_uid is None:
            graph_obj = getattr(self, "graph", None)
            raw_uid = getattr(graph_obj, "user_id", None)
        trusted_uid = str(raw_uid or "").strip()
        if not trusted_uid or trusted_uid.lower() == "none" or not _RE_SCOPE_TOKEN.fullmatch(trusted_uid):
            msg = "Trusted runtime _user_id (or graph.user_id) is required for tenant cache isolation."
            raise ValueError(msg)

        raw_sub = str(getattr(self, "tenant_scope", "default-tenant") or "default-tenant").strip() or "default-tenant"
        if not _RE_SCOPE_TOKEN.fullmatch(raw_sub):
            msg = "Invalid characters in tenant_scope."
            raise ValueError(msg)
        return f"{trusted_uid}:{raw_sub}", raw_sub

    def _run_cache_lookup(self) -> dict[str, object]:
        """Execute or reuse the semantic cache lookup/seed operation for the current component state."""
        raw_q = getattr(self, "query_text", "")
        query_str = getattr(raw_q, "text", str(raw_q or ""))
        raw_seed = getattr(self, "response_to_seed", "")
        seed_str = getattr(raw_seed, "text", str(raw_seed or "")).strip()
        isolation_key, sub_scope = self._resolve_trusted_isolation_scope()
        raw_threshold = getattr(self, "distance_threshold", None)
        threshold = 0.2 if raw_threshold is None else float(raw_threshold)
        if threshold < 0.0:
            msg = f"distance_threshold must be >= 0.0, got {threshold}."
            raise ValueError(msg)
        raw_dim = getattr(self, "cache_dim", _DEFAULT_CACHE_DIM)
        dim = _DEFAULT_CACHE_DIM if raw_dim is None else int(raw_dim)

        exec_sig = (isolation_key, query_str, seed_str, threshold, dim)
        cached_sig = getattr(self, "_last_exec_signature", None)
        cached_res = getattr(self, "_last_exec_result", None)
        if cached_sig == exec_sig and isinstance(cached_res, dict):
            return dict(cached_res)

        q_vec = _derive_deterministic_embedding(query_str, dim=dim)
        kv_hash, worker_id = compute_kv_prefix_hash64(query_str)

        best_dist = float("inf")
        best_entry: dict[str, object] | None = None
        hit_response = ""
        cache_hit = False

        with _CACHE_LOCK:
            bucket = _TENANT_CACHE_ARENA.get(isolation_key, [])
            for entry in bucket:
                e_vec = entry.get("vector")
                if isinstance(e_vec, list) and len(e_vec) == len(q_vec):
                    dist = _l2_distance_squared(q_vec, e_vec)
                    exact_ok = threshold > 0.0 or str(entry.get("query", "")) == query_str
                    if exact_ok and dist <= threshold and dist < best_dist:
                        best_dist = dist
                        best_entry = entry

            if best_entry is not None:
                existing_resp = str(best_entry.get("response", ""))
                if seed_str and seed_str != existing_resp:
                    best_entry["vector"] = q_vec
                    best_entry["response"] = seed_str
                    best_entry["kv_prefix_hash"] = kv_hash
                    best_entry["query"] = query_str
                    hit_response = seed_str
                    cache_hit = False
                else:
                    hit_response = existing_resp
                    cache_hit = True
            elif seed_str:
                write_bucket = _get_tenant_bucket_unlocked(isolation_key)
                if len(write_bucket) >= _MAX_ENTRIES_PER_TENANT:
                    write_bucket.pop(0)
                write_bucket.append(
                    {
                        "vector": q_vec,
                        "response": seed_str,
                        "kv_prefix_hash": kv_hash,
                        "query": query_str,
                    }
                )
                hit_response = seed_str
            active_scopes = len(_TENANT_CACHE_ARENA)

        meta: dict[str, object] = {
            "cache_hit": cache_hit,
            "tenant_scope": sub_scope,
            "isolation_key": isolation_key,
            "max_tenant_scopes": _MAX_TENANT_SCOPES,
            "max_entries_per_tenant": _MAX_ENTRIES_PER_TENANT,
            "active_tenant_scopes": active_scopes,
            "distance": round(best_dist, 6) if math.isfinite(best_dist) else None,
            "cached_response": hit_response,
            "kv_prefix_hash": kv_hash,
            "x-silicium-kv-prefix-hash": kv_hash,
            "worker_id": worker_id,
            "engine_backend": NATIVE_CACHE_BACKEND,
        }
        self._last_exec_signature = exec_sig
        self._last_exec_result = dict(meta)
        self.status = meta
        return meta

    def lookup_cached_message(self) -> Message:
        """Return the cached or seeded response Message."""
        meta = self._run_cache_lookup()
        return Message(text=str(meta.get("cached_response", "")))

    def build_cache_metadata(self) -> Data:
        """Return structured semantic cache hit/miss and KV-prefix affinity Data."""
        meta = self._run_cache_lookup()
        return Data(data=meta)
