# SPDX-License-Identifier: MIT
"""Unit tests for the Langflow `lfx_bundles.silicium` bundle components."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _ensure_silicium_bundle_importable() -> None:
    """Register `lfx_bundles.silicium` in `sys.modules` when running from standalone compliance directories."""
    here = Path(__file__).resolve().parent
    bundle_src = here.parents[1] / "src"
    if (bundle_src / "lfx_bundles").is_dir() and str(bundle_src) not in sys.path:
        sys.path.insert(0, str(bundle_src))
    if (here / "langflow_silicium_init.py").is_file() and "lfx_bundles.silicium" not in sys.modules:
        lfx_pkg = types.ModuleType("lfx_bundles")
        lfx_pkg.__path__ = [str(here)]  # type: ignore[attr-defined]
        sys.modules["lfx_bundles"] = lfx_pkg
        init_spec = importlib.util.spec_from_file_location(
            "lfx_bundles.silicium",
            here / "langflow_silicium_init.py",
            submodule_search_locations=[str(here)],
        )
        assert init_spec is not None
        assert init_spec.loader is not None
        init_mod = importlib.util.module_from_spec(init_spec)
        sys.modules["lfx_bundles.silicium"] = init_mod
        lfx_pkg.silicium = init_mod  # type: ignore[attr-defined]
        for mod_attr, fname in (
            ("silicium_pii_guardrail", "langflow_silicium_pii_guardrail.py"),
            ("silicium_semantic_cache", "langflow_silicium_semantic_cache.py"),
            ("silicium_vector_store", "langflow_silicium_vector_store.py"),
        ):
            spec = importlib.util.spec_from_file_location(f"lfx_bundles.silicium.{mod_attr}", here / fname)
            assert spec is not None
            assert spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"lfx_bundles.silicium.{mod_attr}"] = mod
            sys.modules[mod_attr] = mod
            spec.loader.exec_module(mod)
            setattr(init_mod, mod_attr, mod)
        init_spec.loader.exec_module(init_mod)


_ensure_silicium_bundle_importable()

import lfx_bundles.silicium as silicium_bundle  # noqa: E402
from lfx_bundles.silicium.silicium_pii_guardrail import SiliciumPiiGuardrailComponent  # noqa: E402
from lfx_bundles.silicium.silicium_semantic_cache import (  # noqa: E402
    SiliciumSemanticCacheComponent,
    reset_semantic_cache_arena,
)
from lfx_bundles.silicium.silicium_vector_store import SiliciumVectorStoreComponent  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_semantic_cache_around_each_test() -> object:
    """Reset the semantic cache arena before and after each test, including on failure."""
    reset_semantic_cache_arena()
    try:
        yield
    finally:
        reset_semantic_cache_arena()


def test_silicium_bundle_lazy_exports() -> None:
    """Verify `__all__` and lazy attribute exports on `lfx_bundles.silicium`."""
    assert set(silicium_bundle.__all__) == {
        "SiliciumPiiGuardrailComponent",
        "SiliciumSemanticCacheComponent",
        "SiliciumVectorStoreComponent",
    }
    assert silicium_bundle.SiliciumPiiGuardrailComponent is SiliciumPiiGuardrailComponent
    assert silicium_bundle.SiliciumSemanticCacheComponent is SiliciumSemanticCacheComponent
    assert silicium_bundle.SiliciumVectorStoreComponent is SiliciumVectorStoreComponent


def test_silicium_pii_guardrail_mask_block_audit_and_all_categories() -> None:
    """Verify masking (including full PEM blocks), blocking, clean allow, audit mode, and all 12 categories."""
    # Synthetic Luhn-valid test number assembled at runtime to avoid static PAN scanners
    synthetic_luhn_cc = f"{4532}{151:04d}{1283}{366:04d}"
    pem_label = "RSA PRIVATE KEY"
    pem_block = (
        f"-----BEGIN {pem_label}-----\nMIIEpAIBAAKCAQEA0123456789SECRETKEYMATERIALBODY\n-----END {pem_label}-----"
    )
    comp = SiliciumPiiGuardrailComponent()
    comp.set(
        input_text=(
            f"Contact ceo@example.com with token {'gh' + 'p_1234567890abcdefghijklmnopqrstuvwx'} "
            f"card {synthetic_luhn_cc} order 1234567890123456\n{pem_block}"
        ),
        pii_policy="mask",
    )
    msg = comp.build_guarded_message()
    report = comp.build_audit_report()
    assert "[SILICIUM_REDACTED_EMAIL]" in msg.text
    assert "[SILICIUM_REDACTED_SECRET]" in msg.text
    assert "[SILICIUM_REDACTED_PII]" in msg.text
    assert "MIIEpAIBAAKCAQEA0123456789SECRETKEYMATERIALBODY" not in msg.text
    assert "END RSA PRIVATE KEY" not in msg.text
    assert "1234567890123456" in msg.text
    assert "EMAIL" in report.data["categories"]
    assert "GITHUB_TOKEN" in report.data["categories"]
    assert "CREDIT_CARD_LUHN" in report.data["categories"]
    assert "PRIVATE_KEY_PEM" in report.data["categories"]
    assert report.data["action"] == "REDACT"
    assert report.data["engine_backend"] in {"silicium_c_abi_simd", "python_portable_swar"}
    assert "output_text" not in report.data

    # Verify all remaining PII/secret categories and audit policy
    sample_tokens = [
        "user@example.org",
        synthetic_luhn_cc,
        "123-45-6789",
        "+1-415-555-2671",
        "192.168.1.42",
        "AKI" + "A1234567890ABCDEF",
        "s" + "k-proj1234567890abcdefghij",
        "gh" + "p_1234567890abcdefghijklmnopqrstuvwx",
        "sk_" + "live_1234567890abcdefghij",
        pem_block,
        "ey" + "JhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJlMTIzNDU2",
        "DE89370400440532013000",
    ]
    all_cats_input = " ".join(sample_tokens)
    audit_comp = SiliciumPiiGuardrailComponent()
    audit_comp.set(input_text=all_cats_input, pii_policy="audit")
    audit_msg = audit_comp.build_guarded_message()
    audit_rep = audit_comp.build_audit_report()
    assert audit_rep.data["action"] == "AUDIT_LOG"
    assert audit_msg.text == all_cats_input
    assert "output_text" not in audit_rep.data
    assert len(audit_rep.data["categories"]) == 12

    # Verify all 5 GitHub token prefixes (ghp_, gho_, ghu_, ghs_, ghr_) and github_pat_
    for gh_prefix in ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_" + "pat_"):
        gh_comp = SiliciumPiiGuardrailComponent()
        gh_comp.set(input_text=f"token {gh_prefix}{'a' * 24}", pii_policy="mask")
        gh_msg = gh_comp.build_guarded_message()
        gh_rep = gh_comp.build_audit_report()
        assert "[SILICIUM_REDACTED_SECRET]" in gh_msg.text
        assert "GITHUB_TOKEN" in gh_rep.data["categories"]

    # Clean text under block policy is allowed
    clean_comp = SiliciumPiiGuardrailComponent()
    clean_comp.set(input_text="Pure technical benchmark telemetry summary.", pii_policy="block")
    clean_msg = clean_comp.build_guarded_message()
    clean_rep = clean_comp.build_audit_report()
    assert clean_msg.text == "Pure technical benchmark telemetry summary."
    assert clean_rep.data["action"] == "ALLOW"

    block_comp = SiliciumPiiGuardrailComponent()
    block_comp.set(input_text="Email ceo@example.com", pii_policy="block")
    with pytest.raises(ValueError, match="SiliciumPiiGuardrail blocked message"):
        block_comp.build_guarded_message()

    budget_comp = SiliciumPiiGuardrailComponent()
    budget_comp.set(input_text="A" * 64, pii_policy="mask", max_tokens=2)
    with pytest.raises(ValueError, match="token budget exceeded"):
        budget_comp.build_guarded_message()


def test_silicium_semantic_cache_tenant_isolation_and_eviction() -> None:
    """Verify shared output execution, seed updates, trusted user isolation, thresholds, and 256-scope eviction."""
    reset_semantic_cache_arena()
    try:
        seed_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        seed_comp.set(
            query_text="What is the Silicium vector throughput?",
            response_to_seed="369,836 QPS on SIFT-1M.",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        # Calling both output methods in the same execution shares one lookup result
        seeded_msg = seed_comp.lookup_cached_message()
        first_meta = seed_comp.build_cache_metadata()
        assert seeded_msg.text == "369,836 QPS on SIFT-1M."
        assert first_meta.data["cache_hit"] is False
        assert first_meta.data["cached_response"] == "369,836 QPS on SIFT-1M."
        assert first_meta.data["max_entries_per_tenant"] == 1024

        hit_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        hit_comp.set(
            query_text="What is the Silicium vector throughput?",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        hit_meta = hit_comp.build_cache_metadata()
        assert hit_meta.data["cache_hit"] is True
        assert hit_meta.data["cached_response"] == "369,836 QPS on SIFT-1M."

        # Updating an existing cached query with a new explicit response_to_seed supersedes the old entry
        reseed_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        reseed_comp.set(
            query_text="What is the Silicium vector throughput?",
            response_to_seed="369,836 QPS @ 99.1% Recall@10.",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        reseed_meta = reseed_comp.build_cache_metadata()
        assert reseed_meta.data["cache_hit"] is False
        assert reseed_meta.data["cached_response"] == "369,836 QPS @ 99.1% Recall@10."

        verify_reseed = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        verify_reseed.set(
            query_text="What is the Silicium vector throughput?",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        assert verify_reseed.lookup_cached_message().text == "369,836 QPS @ 99.1% Recall@10."

        # Hit and miss with nonzero embedding distances on both sides of a nonzero threshold
        near_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        near_comp.set(
            query_text="What is the Silicium vector throughput today?",
            tenant_scope="tenant-alpha",
            distance_threshold=0.80,
        )
        near_meta = near_comp.build_cache_metadata()
        assert near_meta.data["cache_hit"] is True
        nonzero_dist = float(near_meta.data["distance"])
        assert nonzero_dist > 0.0

        # Seeding a near-neighbor query inserts a distinct entry without overwriting the original neighbor
        near_seed_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        near_seed_comp.set(
            query_text="What is the Silicium vector throughput today?",
            response_to_seed="369,836 QPS today.",
            tenant_scope="tenant-alpha",
            distance_threshold=0.80,
        )
        assert near_seed_comp.build_cache_metadata().data["cache_hit"] is False
        orig_exact = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        orig_exact.set(
            query_text="What is the Silicium vector throughput?",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        assert orig_exact.lookup_cached_message().text == "369,836 QPS @ 99.1% Recall@10."
        new_exact = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        new_exact.set(
            query_text="What is the Silicium vector throughput today?",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        assert new_exact.lookup_cached_message().text == "369,836 QPS today."

        tight_nonzero_miss = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        tight_nonzero_miss.set(
            query_text="What is the Silicium vector throughput tomorrow?",
            tenant_scope="tenant-alpha",
            distance_threshold=max(0.0001, nonzero_dist * 0.5),
        )
        assert tight_nonzero_miss.build_cache_metadata().data["cache_hit"] is False

        strict_miss_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        strict_miss_comp.set(
            query_text="What is the Silicium vector throughput!",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        assert strict_miss_comp.build_cache_metadata().data["cache_hit"] is False

        # Different user identity cannot read user-alpha's cache even with the same tenant_scope
        other_user_comp = SiliciumSemanticCacheComponent(_user_id="user-beta")
        other_user_comp.set(
            query_text="What is the Silicium vector throughput?",
            tenant_scope="tenant-alpha",
        )
        assert other_user_comp.build_cache_metadata().data["cache_hit"] is False

        # Same user identity with a different tenant_scope is isolated from tenant-alpha
        other_scope_miss = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        other_scope_miss.set(
            query_text="What is the Silicium vector throughput?",
            tenant_scope="tenant-beta",
            distance_threshold=0.0,
        )
        assert other_scope_miss.build_cache_metadata().data["cache_hit"] is False

        other_scope_seed = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        other_scope_seed.set(
            query_text="What is the Silicium vector throughput?",
            response_to_seed="tenant-beta independent response",
            tenant_scope="tenant-beta",
            distance_threshold=0.0,
        )
        assert other_scope_seed.build_cache_metadata().data["cache_hit"] is False

        alpha_check = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        alpha_check.set(
            query_text="What is the Silicium vector throughput?",
            tenant_scope="tenant-alpha",
            distance_threshold=0.0,
        )
        assert alpha_check.lookup_cached_message().text == "369,836 QPS @ 99.1% Recall@10."

        beta_check = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        beta_check.set(
            query_text="What is the Silicium vector throughput?",
            tenant_scope="tenant-beta",
            distance_threshold=0.0,
        )
        assert beta_check.lookup_cached_message().text == "tenant-beta independent response"

        # Reject missing trusted runtime _user_id and invalid cache_dim < 8 or > 4096
        no_uid_comp = SiliciumSemanticCacheComponent()
        no_uid_comp.set(query_text="test")
        with pytest.raises(ValueError, match="Trusted runtime _user_id"):
            no_uid_comp.build_cache_metadata()

        bad_dim_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        bad_dim_comp.set(query_text="test", cache_dim=1)
        with pytest.raises(ValueError, match="cache_dim must be >= 8"):
            bad_dim_comp.build_cache_metadata()

        huge_dim_comp = SiliciumSemanticCacheComponent(_user_id="user-alpha")
        huge_dim_comp.set(query_text="test", cache_dim=8192)
        with pytest.raises(ValueError, match="cache_dim must be >= 8 and <= 4096"):
            huge_dim_comp.build_cache_metadata()

        # Per-scope FIFO eviction when one scope exceeds its 1,024-entry limit
        reset_semantic_cache_arena()
        for entry_idx in range(1025):
            fifo_comp = SiliciumSemanticCacheComponent(_user_id="fifo-user")
            fifo_comp.set(
                query_text=f"scope-fifo-query-{entry_idx}",
                response_to_seed=f"scope-fifo-answer-{entry_idx}",
                tenant_scope="fifo-scope",
                cache_dim=8,
                distance_threshold=0.0,
            )
            fifo_meta = fifo_comp.build_cache_metadata()
            assert fifo_meta.data["cache_hit"] is False
            assert int(fifo_meta.data["max_entries_per_tenant"]) == 1024

        evicted_first_entry = SiliciumSemanticCacheComponent(_user_id="fifo-user")
        evicted_first_entry.set(
            query_text="scope-fifo-query-0",
            tenant_scope="fifo-scope",
            cache_dim=8,
            distance_threshold=0.0,
        )
        assert evicted_first_entry.build_cache_metadata().data["cache_hit"] is False

        retained_second_entry = SiliciumSemanticCacheComponent(_user_id="fifo-user")
        retained_second_entry.set(
            query_text="scope-fifo-query-1",
            tenant_scope="fifo-scope",
            cache_dim=8,
            distance_threshold=0.0,
        )
        assert retained_second_entry.build_cache_metadata().data["cache_hit"] is True

        retained_latest_entry = SiliciumSemanticCacheComponent(_user_id="fifo-user")
        retained_latest_entry.set(
            query_text="scope-fifo-query-1024",
            tenant_scope="fifo-scope",
            cache_dim=8,
            distance_threshold=0.0,
        )
        assert retained_latest_entry.build_cache_metadata().data["cache_hit"] is True

        # Fill 256 tenant scopes, verify read-only miss does not evict, then seed 257th and verify FIFO eviction
        reset_semantic_cache_arena()
        for idx in range(256):
            ev_comp = SiliciumSemanticCacheComponent(_user_id=f"evict-user-{idx}")
            ev_comp.set(query_text="ping", response_to_seed=f"pong-{idx}", distance_threshold=0.0)
            ev_meta = ev_comp.build_cache_metadata()
            assert int(ev_meta.data["active_tenant_scopes"]) == idx + 1

        # Read-only miss on an unseen tenant scope does not create a bucket or evict evict-user-0
        ro_miss = SiliciumSemanticCacheComponent(_user_id="read-only-unseen")
        ro_miss.set(query_text="ping", distance_threshold=0.0)
        assert ro_miss.build_cache_metadata().data["cache_hit"] is False

        still_here = SiliciumSemanticCacheComponent(_user_id="evict-user-0")
        still_here.set(query_text="ping", distance_threshold=0.0)
        assert still_here.build_cache_metadata().data["cache_hit"] is True

        # Seeding a 257th scope evicts evict-user-0 while keeping evict-user-255 available
        overflow_comp = SiliciumSemanticCacheComponent(_user_id="evict-user-256")
        overflow_comp.set(query_text="ping", response_to_seed="pong-256", distance_threshold=0.0)
        overflow_meta = overflow_comp.build_cache_metadata()
        assert int(overflow_meta.data["active_tenant_scopes"]) == 256

        evicted_oldest = SiliciumSemanticCacheComponent(_user_id="evict-user-0")
        evicted_oldest.set(query_text="ping", distance_threshold=0.0)
        assert evicted_oldest.build_cache_metadata().data["cache_hit"] is False

        retained_newer = SiliciumSemanticCacheComponent(_user_id="evict-user-255")
        retained_newer.set(query_text="ping", distance_threshold=0.0)
        assert retained_newer.build_cache_metadata().data["cache_hit"] is True
    finally:
        reset_semantic_cache_arena()


def test_silicium_vector_store_ingest_search_and_negative_cases() -> None:
    """Verify L2 search, cosine ranking, default-embedding search, empty store, and dimension mismatch."""
    from lfx_bundles.silicium.silicium_vector_store import Data, _InMemorySiliciumVectorStore

    class _TupleEmbedding:
        """Deterministic 8-D test embedding provider returning tuples."""

        def __init__(self) -> None:
            """Initialize batch call counter."""
            self.batch_calls = 0

        def embed_query(self, text: str) -> tuple[float, ...]:
            """Return directional 8-D vectors for L2 and cosine ranking tests."""
            if "exact-target" in text:
                return (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            if "partial-match" in text:
                return (0.8, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            if "HNSW" in text:
                return (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            return (0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        def embed_documents(self, texts: list[str]) -> list[tuple[float, ...]]:
            """Batch-embed document texts using `embed_query`."""
            self.batch_calls += 1
            return [self.embed_query(t) for t in texts]

    emb_provider = _TupleEmbedding()
    vs_comp = SiliciumVectorStoreComponent()
    vs_comp.set(
        collection_name="test_langflow_col",
        distance_metric="l2",
        embedding=emb_provider,
        ingest_data=[
            Data(data={"text": "Zero-copy SIMD JSON parsing at 9.42 GB/s"}),
            Data(data={"text": "HNSW semantic cache lookup in under 50 microseconds"}),
        ],
        search_query="HNSW semantic cache",
        number_of_results=1,
    )
    results = vs_comp.search_documents()
    assert len(results) == 1
    assert emb_provider.batch_calls == 1
    assert "HNSW" in results[0].text or "HNSW" in str(results[0].data.get("text", ""))

    # Populated cosine search test asserting result ranking across multiple candidates
    cosine_comp = SiliciumVectorStoreComponent()
    cosine_comp.set(
        collection_name="test_cosine_ranking",
        distance_metric="cosine",
        embedding=emb_provider,
        ingest_data=[
            Data(data={"text": "orthogonal unrelated document"}),
            Data(data={"text": "partial-match cosine candidate"}),
            Data(data={"text": "exact-target cosine winner"}),
        ],
        search_query="exact-target query",
        number_of_results=2,
    )
    cosine_results = cosine_comp.search_documents()
    assert len(cosine_results) == 2
    first_cosine_txt = cosine_results[0].text or str(cosine_results[0].data.get("text", ""))
    second_cosine_txt = cosine_results[1].text or str(cosine_results[1].data.get("text", ""))
    assert "exact-target cosine winner" in first_cosine_txt
    assert "partial-match cosine candidate" in second_cosine_txt

    # Populated search test without an embedding provider (deterministic fallback embedding)
    no_emb_comp = SiliciumVectorStoreComponent()
    no_emb_comp.set(
        collection_name="test_no_embedding_provider",
        distance_metric="cosine",
        embedding=None,
        ingest_data=[
            Data(data={"text": "PostgreSQL analytical query execution"}),
            Data(data={"text": "Silicium SIMD JSON parser throughput"}),
        ],
        search_query="Silicium SIMD JSON parser throughput",
        number_of_results=1,
    )
    no_emb_results = no_emb_comp.search_documents()
    assert len(no_emb_results) == 1
    no_emb_txt = no_emb_results[0].text or str(no_emb_results[0].data.get("text", ""))
    assert "Silicium SIMD JSON parser throughput" in no_emb_txt

    # Blank query and empty vector store return empty list
    vs_comp.set(search_query="   ")
    assert vs_comp.search_documents() == []

    empty_comp = SiliciumVectorStoreComponent()
    empty_comp.set(collection_name="empty_col", ingest_data=[], search_query="HNSW")
    assert empty_comp.search_documents() == []

    # Dimension mismatch between stored vectors and query vector raises ValueError
    class _ChangingDimEmbedding:
        """Test embedding provider whose output dimension changes on the second call."""

        def __init__(self) -> None:
            """Initialize call counter."""
            self.calls = 0

        def embed_query(self, _text: str) -> list[float]:
            """Return 8-D vector first, then 4-D vector."""
            self.calls += 1
            return [1.0] * 8 if self.calls == 1 else [1.0] * 4

    raw_store = _InMemorySiliciumVectorStore(embedding=_ChangingDimEmbedding())
    raw_store.add_documents([Data(data={"text": "doc1"})])
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        raw_store.similarity_search("query")


def test_silicium_framework_discovery_and_component_set_contract() -> None:
    """Discover Silicium components via `load_lfx_bundles_extensions` and exercise them in the framework."""
    from lfx_bundles.silicium.silicium_vector_store import Data

    reset_semantic_cache_arena()
    try:
        loaded_classes: dict[str, type] = {}
        if importlib.util.find_spec("lfx") is not None:
            from lfx.extension import load_lfx_bundles_extensions

            silicium_dir = Path(silicium_bundle.__file__).resolve().parent
            bundles_root_dir = silicium_dir.parent
            claimed = {
                child.name: ("seed", str(child))
                for child in bundles_root_dir.iterdir()
                if child.is_dir() and child.name != "silicium"
            }
            ep = types.SimpleNamespace(name="lfx_bundles", value="lfx_bundles", dist=None)
            bundle_results = load_lfx_bundles_extensions(entry_points=[ep], claimed_bundles=claimed)
            silicium_result = next(res for res in bundle_results if res.bundle == "silicium")
            assert silicium_result.ok is True
            for comp in silicium_result.components:
                loaded_classes[comp.class_name] = comp.klass
        else:
            for comp_name, mod_name in silicium_bundle._dynamic_imports.items():
                cls = silicium_bundle.import_mod(
                    comp_name,
                    mod_name,
                    silicium_bundle.__spec__.parent if silicium_bundle.__spec__ else "lfx_bundles.silicium",
                )
                assert cls is getattr(silicium_bundle, comp_name)
                loaded_classes[comp_name] = cls

        assert set(loaded_classes) == set(silicium_bundle.__all__)
        for comp_name, cls in loaded_classes.items():
            inst = cls()
            assert inst.name == comp_name
            assert isinstance(inst.display_name, str)
            assert len(inst.display_name) > 0
            assert isinstance(inst.description, str)
            assert len(inst.description) > 0

        guard_inst = loaded_classes["SiliciumPiiGuardrailComponent"]()
        guard_inst.set(input_text="Contact dev@example.com", pii_policy="mask")
        assert "[SILICIUM_REDACTED_EMAIL]" in guard_inst.build_guarded_message().text
        assert guard_inst.build_audit_report().data["action"] == "REDACT"

        cache_inst = loaded_classes["SiliciumSemanticCacheComponent"](_user_id="framework-user")
        returned = cache_inst.set(query_text="hello framework", response_to_seed="world", distance_threshold=0.0)
        assert returned is cache_inst
        if hasattr(cache_inst, "_parameters") and isinstance(cache_inst._parameters, dict):
            assert cache_inst._parameters.get("query_text") == "hello framework"
        assert cache_inst.lookup_cached_message().text == "world"

        vs_inst = loaded_classes["SiliciumVectorStoreComponent"]()
        vs_inst.set(
            collection_name="framework_col",
            distance_metric="cosine",
            ingest_data=[Data(data={"text": "bundle loader vector document"})],
            search_query="bundle loader vector document",
            number_of_results=1,
        )
        found = vs_inst.search_documents()
        assert len(found) == 1
    finally:
        reset_semantic_cache_arena()


if __name__ == "__main__":
    test_silicium_bundle_lazy_exports()
    test_silicium_pii_guardrail_mask_block_audit_and_all_categories()
    test_silicium_semantic_cache_tenant_isolation_and_eviction()
    test_silicium_vector_store_ingest_search_and_negative_cases()
    test_silicium_framework_discovery_and_component_set_contract()
