"""Regression tests for global-variable redaction in ``ComponentVertex``.

The base ``Vertex._update_built_object_and_artifacts`` invokes
``_redact_resolved_global_values`` to mask resolved global-variable values in
``self.logs``, ``self.artifacts``, and ``self.artifacts_raw`` before they reach
the UI. ``ComponentVertex`` (and ``InterfaceVertex`` via inheritance) replaces
that method entirely and previously skipped the redaction hook, so the resolved
secret could still leak through built-in components and the
``ResultData.results`` payload that the playground IO modal renders.

These tests pin the redaction path on the override and on ``finalize_build``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
from lfx.graph.vertex.vertex_types import ComponentVertex, CustomComponentVertex


def _make_component_vertex() -> ComponentVertex:
    """Construct a ``ComponentVertex`` without running the full ``__init__``.

    The full constructor walks the graph and parses node data; for these unit
    tests we only need the redaction hook to find populated attributes, so we
    seed a minimal state directly.
    """
    vertex = ComponentVertex.__new__(ComponentVertex)
    vertex.built_object = {}
    vertex.artifacts = {}
    vertex.artifacts_raw = {}
    vertex.artifacts_type = {}
    vertex.logs = {}
    vertex.results = {}
    vertex.outputs_logs = {}
    vertex._resolved_global_values = {}
    vertex.id = "test-component-vertex"
    vertex.display_name = "Test Component"
    vertex.is_interface_component = False
    vertex.built_result = None
    return vertex


def test_update_built_object_redacts_logs_and_artifacts_two_tuple():
    """Two-tuple result shape: ``(built_object, artifacts)``.

    Confirms the override now masks resolved values that landed in artifacts.
    """
    vertex = _make_component_vertex()
    secret = "sk-leaked-credential"  # noqa: S105  # pragma: allowlist secret
    vertex._resolved_global_values = {secret: "OPENAI_API_KEY"}  # pragma: allowlist secret

    built_object = {"text": f"echoing {secret} back"}
    artifacts = {"raw": secret, "summary": f"contains {secret}"}

    vertex._update_built_object_and_artifacts((built_object, artifacts))

    # Artifacts surfaced to the UI must be masked.
    assert secret not in str(vertex.artifacts)
    assert "[REDACTED: OPENAI_API_KEY]" in str(vertex.artifacts)

    # ``built_object``/``self.results`` remain raw — downstream vertices
    # consume those over edges and require the real values.
    assert vertex.built_object["text"] == f"echoing {secret} back"
    assert vertex.results["text"] == f"echoing {secret} back"


def test_update_built_object_redacts_logs_three_tuple():
    """Three-tuple result shape: ``(custom_component, built_object, artifacts)``.

    Confirms that ``self.logs`` and ``self.artifacts_raw`` (populated only on
    this branch) get redacted.
    """
    vertex = _make_component_vertex()
    secret = "private-token-xyz"  # noqa: S105  # pragma: allowlist secret
    vertex._resolved_global_values = {secret: "PRIVATE_TOKEN"}  # pragma: allowlist secret

    custom_component = Mock()
    custom_component.get_output_logs.return_value = {"text": [{"message": f"resolved to {secret}", "type": "text"}]}

    built_object = {"text": f"output uses {secret}"}
    artifacts = {
        "text": {"raw": secret, "type": "text", "repr": f"Text({secret})"},
    }

    vertex._update_built_object_and_artifacts((custom_component, built_object, artifacts))

    assert secret not in str(vertex.logs)
    assert "[REDACTED: PRIVATE_TOKEN]" in str(vertex.logs)
    assert secret not in str(vertex.artifacts_raw)
    assert "[REDACTED: PRIVATE_TOKEN]" in str(vertex.artifacts_raw)
    assert secret not in str(vertex.artifacts)


def test_update_built_object_no_resolved_globals_is_passthrough():
    """When the vertex has no resolved global values, payloads are untouched."""
    vertex = _make_component_vertex()
    payload = "regular output value"
    built_object = {"text": payload}
    artifacts = {"summary": payload}

    vertex._update_built_object_and_artifacts((built_object, artifacts))

    assert vertex.built_object["text"] == payload
    assert vertex.artifacts["summary"] == payload
    assert vertex.results["text"] == payload


def _seed_finalize_build_state(vertex: ComponentVertex, built_result: Any) -> None:
    """Seed the minimal attributes that ``finalize_build`` reads."""
    vertex.built_result = built_result
    vertex.built_object = built_result if isinstance(built_result, dict) else {}
    vertex.outputs_logs = {}
    vertex.logs = {}
    vertex.artifacts = {}
    # Stub helpers ``finalize_build`` calls.
    vertex.extract_messages_from_artifacts = lambda _result_dict: []  # type: ignore[method-assign]
    vertex._extract_token_usage = dict  # type: ignore[method-assign]


def test_finalize_build_redacts_results_in_result_data():
    """``ResultData.results`` (rendered in the IO modal) must be masked.

    Echo components like Text Input return the resolved global value as their
    output. ``finalize_build`` builds the ``ResultData`` payload that the
    frontend renders at ``data.results.text`` — that field must not surface the
    resolved secret even though ``self.built_object`` keeps it for downstream
    consumption.
    """
    vertex = _make_component_vertex()
    secret = "sk-text-input-secret"  # noqa: S105  # pragma: allowlist secret
    vertex._resolved_global_values = {secret: "MY_TEXT_VAR"}  # pragma: allowlist secret
    _seed_finalize_build_state(vertex, built_result={"text": secret, "result": secret})

    vertex.finalize_build()

    assert vertex.result is not None
    results = vertex.result.results
    assert results["text"] != secret
    assert results["text"] == "[REDACTED: MY_TEXT_VAR]"
    assert results["result"] == "[REDACTED: MY_TEXT_VAR]"
    # ``built_object``/``built_result`` remain raw for downstream edges.
    assert vertex.built_object["text"] == secret
    assert vertex.built_result["text"] == secret


def test_finalize_build_redacts_messages_payload():
    """Chat messages extracted from artifacts are also masked."""
    vertex = _make_component_vertex()
    secret = "sk-chat-secret"  # noqa: S105  # pragma: allowlist secret
    vertex._resolved_global_values = {secret: "CHAT_KEY"}  # pragma: allowlist secret
    _seed_finalize_build_state(vertex, built_result={"text": "hello"})
    # Inject a fake message that echoes the secret.
    vertex.extract_messages_from_artifacts = lambda _r: [  # type: ignore[method-assign]
        {"message": f"key={secret}", "sender": "User", "type": "object"}
    ]

    vertex.finalize_build()

    assert vertex.result is not None
    messages = vertex.result.messages
    assert secret not in str(messages)
    assert "[REDACTED: CHAT_KEY]" in str(messages)


def test_finalize_build_no_resolved_globals_passthrough():
    """No resolved globals => ``ResultData.results`` is returned unchanged."""
    vertex = _make_component_vertex()
    payload = "plain output without any secret"
    _seed_finalize_build_state(vertex, built_result={"text": payload})

    vertex.finalize_build()

    assert vertex.result is not None
    assert vertex.result.results["text"] == payload


def _make_custom_component_vertex() -> CustomComponentVertex:
    """Build a ``CustomComponentVertex`` without invoking its full ``__init__``.

    ``CustomComponentVertex`` extends ``Vertex`` directly (not
    ``ComponentVertex``), so it relies on the base ``finalize_build`` for the
    redaction hook. That makes this the relevant subclass to pin: a custom
    component with a ``load_from_db`` SecretStr input would otherwise leak the
    resolved value through ``ResultData.results``.
    """
    vertex = CustomComponentVertex.__new__(CustomComponentVertex)
    vertex.built_object = {}
    vertex.built_result = None
    vertex.artifacts = {}
    vertex.artifacts_raw = {}
    vertex.artifacts_type = {}
    vertex.logs = {}
    vertex.results = {}
    vertex.outputs_logs = {}
    vertex._resolved_global_values = {}
    vertex.id = "test-custom-component-vertex"
    vertex.display_name = "Test Custom Component"
    vertex.is_interface_component = False
    vertex._extract_token_usage = dict  # type: ignore[method-assign]
    return vertex


def test_custom_component_vertex_finalize_build_redacts_results():
    """Custom-component path must mask the resolved value in ``results``.

    ``CustomComponentVertex`` does not override ``finalize_build``; the base
    method is the only place to redact for this subclass. This pins that
    ``[REDACTED: <name>]`` is what reaches ``ResultData.results`` while
    ``built_object`` is preserved for downstream edges.
    """
    vertex = _make_custom_component_vertex()
    secret = "sk-custom-secret-token"  # noqa: S105  # pragma: allowlist secret
    vertex._resolved_global_values = {secret: "MY_CUSTOM_VAR"}  # pragma: allowlist secret
    vertex.built_result = {"text": secret, "result": secret}
    vertex.built_object = {"text": secret, "result": secret}

    vertex.finalize_build()

    assert vertex.result is not None
    assert vertex.result.results["text"] == "[REDACTED: MY_CUSTOM_VAR]"
    assert vertex.result.results["result"] == "[REDACTED: MY_CUSTOM_VAR]"
    # ``built_object`` stays raw — downstream vertices still receive the value.
    assert vertex.built_object["text"] == secret


def test_custom_component_vertex_finalize_build_no_globals_passthrough():
    """No resolved globals => the base ``finalize_build`` passes payloads through."""
    vertex = _make_custom_component_vertex()
    payload = "plain custom-component output"
    vertex.built_result = {"text": payload}
    vertex.built_object = {"text": payload}

    vertex.finalize_build()

    assert vertex.result is not None
    assert vertex.result.results["text"] == payload


def test_finalize_build_still_redacts_after_cache_round_trip():
    """Regression: the frozen-result cache path must preserve ``_resolved_global_values``.

    ``Graph._build_vertex`` writes a minimal ``vertex_dict`` to the chat cache
    for frozen vertices and restores those fields on the next run before
    invoking ``finalize_build``. If ``_resolved_global_values`` is not among
    the persisted keys, the restored vertex has an empty redaction map and
    re-emits the raw resolved value in ``ResultData.results``. This test
    simulates that round trip against a ``CustomComponentVertex`` (whose
    ``finalize_build`` comes from the base class) and pins that ``results``
    is still masked after restoration.
    """
    original = _make_custom_component_vertex()
    secret = "sk-frozen-cache-secret"  # noqa: S105  # pragma: allowlist secret
    original._resolved_global_values = {secret: "FROZEN_VAR"}  # pragma: allowlist secret
    original.built = True
    original.built_object = {"text": secret, "result": secret}
    original.built_result = {"text": secret, "result": secret}
    original.results = {"text": secret, "result": secret}
    original.artifacts = {}
    original.full_data = {}

    # Mirror the ``vertex_dict`` layout written in ``Graph._build_vertex``.
    vertex_dict = {
        "built": original.built,
        "results": original.results,
        "artifacts": original.artifacts,
        "built_object": original.built_object,
        "built_result": original.built_result,
        "full_data": original.full_data,
        "_resolved_global_values": getattr(original, "_resolved_global_values", {}),
    }

    # A fresh vertex restored from the cache dict — mirrors the read path in
    # ``Graph._build_vertex``.
    restored = _make_custom_component_vertex()
    restored.built = vertex_dict["built"]
    restored.artifacts = vertex_dict["artifacts"]
    restored.built_object = vertex_dict["built_object"]
    restored.built_result = vertex_dict["built_result"]
    restored.full_data = vertex_dict["full_data"]
    restored.results = vertex_dict["results"]
    restored._resolved_global_values = vertex_dict.get("_resolved_global_values", {})

    restored.finalize_build()

    assert restored.result is not None
    assert secret not in str(restored.result.results)
    assert restored.result.results["text"] == "[REDACTED: FROZEN_VAR]"
    assert restored.result.results["result"] == "[REDACTED: FROZEN_VAR]"


def test_reset_clears_resolved_global_values():
    """Regression: ``Vertex._reset`` must drop the prior-run redaction map.

    The ``load_from_db`` resolvers (``_record_resolved_global_values`` and
    ``_record_table_resolved_value``) read ``vertex._resolved_global_values``
    and append into it. If a graph instance is reused across runs, the map
    accumulates stale entries from earlier executions: legitimate output text
    that happens to match a previously-resolved secret would still be masked,
    even after the binding was changed or removed. Worse, the stale map is
    then re-persisted into the frozen-result cache. Pin that ``_reset``
    starts each rebuild with a fresh, empty map.
    """
    vertex = _make_component_vertex()
    stale_secret = "stale-secret-from-previous-run"  # noqa: S105  # pragma: allowlist secret
    vertex._resolved_global_values = {stale_secret: "OLD_VAR"}  # pragma: allowlist secret
    # ``_reset`` calls ``build_params`` — bypass it for this isolated test.
    vertex.build_params = lambda: None  # type: ignore[method-assign]

    vertex._reset()

    assert vertex._resolved_global_values == {}


def _restore_vertex_from_cache(vertex: Any, cached_vertex_dict: dict) -> None:
    """Mirror of the restore block in ``Graph._build_vertex``.

    Kept in lockstep with the production code at ``graph/graph/base.py``
    around the ``cached_vertex_dict["_resolved_global_values"]`` line. The
    outer ``except KeyError`` in production turns a missing key into a cache
    miss / rebuild; this helper just propagates the ``KeyError`` so the test
    can assert which keys are required.
    """
    vertex.built = cached_vertex_dict["built"]
    vertex.artifacts = cached_vertex_dict["artifacts"]
    vertex.built_object = cached_vertex_dict["built_object"]
    vertex.built_result = cached_vertex_dict["built_result"]
    vertex.full_data = cached_vertex_dict["full_data"]
    vertex.results = cached_vertex_dict["results"]
    vertex._resolved_global_values = cached_vertex_dict["_resolved_global_values"]


def test_pre_fix_cache_entry_missing_resolved_globals_forces_rebuild():
    """Legacy cache entries without ``_resolved_global_values`` must rebuild.

    Cache entries written by older deploys predate the redaction work and
    do not carry the ``_resolved_global_values`` key. If the restore path
    silently defaulted to an empty map, ``finalize_build`` would emit the
    cached raw ``built_result`` (which contains the resolved secret) with
    no redaction — replaying the original leak one more time per stale
    entry. The restore code subscripts the key directly so a ``KeyError``
    falls through to the outer handler in ``Graph._build_vertex`` that
    forces a rebuild. Pin that contract.
    """
    secret = "raw-cached-secret"  # noqa: S105  # pragma: allowlist secret
    legacy_cached_vertex_dict = {
        "built": True,
        "results": {"text": secret},
        "artifacts": {},
        "built_object": {"text": secret},
        "built_result": {"text": secret},
        "full_data": {},
        # Note: no "_resolved_global_values" — this is a pre-fix entry.
    }
    vertex = _make_component_vertex()

    with pytest.raises(KeyError, match="_resolved_global_values"):
        _restore_vertex_from_cache(vertex, legacy_cached_vertex_dict)


def test_post_fix_cache_entry_restores_and_redacts():
    """A cache entry written by the fixed code restores cleanly and redacts.

    This complements the pre-fix test above: when ``_resolved_global_values``
    is present, the restore helper succeeds and ``finalize_build`` masks the
    cached ``built_result`` using the restored map.
    """
    secret = "post-fix-secret"  # noqa: S105  # pragma: allowlist secret
    cached_vertex_dict = {
        "built": True,
        "results": {"text": secret},
        "artifacts": {},
        "built_object": {"text": secret},
        "built_result": {"text": secret},
        "full_data": {},
        "_resolved_global_values": {secret: "POST_FIX_VAR"},  # pragma: allowlist secret
    }
    vertex = _make_custom_component_vertex()

    _restore_vertex_from_cache(vertex, cached_vertex_dict)
    vertex.finalize_build()

    assert vertex.result is not None
    assert vertex.result.results["text"] == "[REDACTED: POST_FIX_VAR]"


def test_finalize_build_after_reset_does_not_redact_with_stale_map():
    """End-to-end: a rebuild after ``_reset`` must not mask using prior secrets.

    Simulates the cross-run bleed-through: a vertex resolved a global on run
    1, then on run 2 the same vertex outputs a string that happens to contain
    that prior value as a substring (e.g. an end-user typed it back in).
    Without the ``_reset`` fix, run 2's UI output would show
    ``[REDACTED: …]`` for a value that is no longer secret on this run.
    """
    vertex = _make_component_vertex()
    prior_secret = "prior-run-secret-value"  # noqa: S105  # pragma: allowlist secret
    vertex._resolved_global_values = {prior_secret: "OLD_VAR"}  # pragma: allowlist secret
    vertex.build_params = lambda: None  # type: ignore[method-assign]

    vertex._reset()
    # Run 2: no globals are resolved this time. The user's text input
    # legitimately contains the previously-secret string.
    user_input = f"please echo {prior_secret} verbatim"
    _seed_finalize_build_state(vertex, built_result={"text": user_input})

    vertex.finalize_build()

    assert vertex.result is not None
    assert vertex.result.results["text"] == user_input
    assert "[REDACTED" not in vertex.result.results["text"]
