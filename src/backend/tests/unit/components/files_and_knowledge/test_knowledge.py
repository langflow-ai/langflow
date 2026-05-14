"""Tests for the merged :class:`KnowledgeComponent`.

The existing ``test_ingestion.py`` and ``test_retrieval.py`` exercise the
ingest and retrieve code paths end-to-end through the backward-compat
subclass shims (``KnowledgeIngestionComponent`` /
``KnowledgeBaseComponent``); if those keep passing, the merged component's
behavior on the run path is verified by reuse.

This file covers the *new* surface area introduced by the merge:

* the ``mode`` ``TabInput`` exists and defaults to ``MODE_INGEST``;
* ``update_build_config`` toggles ``show`` on the ingest / retrieve input
  groups in lockstep with the selected mode;
* ``update_outputs`` swaps the single visible output between
  ``ingest_result`` (Data) and ``retrieve_result`` (DataFrame);
* the legacy subclasses pin themselves to the right mode at init time.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from lfx.components.files_and_knowledge.ingestion import KnowledgeIngestionComponent
from lfx.components.files_and_knowledge.knowledge import (
    MODE_INGEST,
    MODE_RETRIEVE,
    KnowledgeComponent,
    _is_retrieve_mode,
)
from lfx.components.files_and_knowledge.retrieval import KnowledgeBaseComponent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_config_from_inputs(component: KnowledgeComponent) -> dict:
    """Snapshot the component's declared inputs into a build_config-like dict.

    The frontend hands ``update_build_config`` a dict keyed by input name
    where each value carries ``show`` / ``value`` / ``options`` / etc. This
    helper mirrors that shape from the class-level ``inputs`` declaration so
    the tests don't need a real frontend session.
    """
    build_config: dict = {}
    for inp in component.inputs:
        entry = inp.to_dict() if hasattr(inp, "to_dict") else dict(inp.__dict__)
        # ``show`` may be omitted when the input default is True; make it
        # explicit so the toggle assertions read cleanly.
        entry.setdefault("show", getattr(inp, "show", True))
        entry.setdefault("value", getattr(inp, "value", None))
        build_config[inp.name] = entry
    return build_config


def _mode_options(component: KnowledgeComponent) -> list[str]:
    mode_input = next((i for i in component.inputs if i.name == "mode"), None)
    assert mode_input is not None, "KnowledgeComponent must declare a 'mode' input"
    return list(mode_input.options or [])


# ---------------------------------------------------------------------------
# Structural assertions on the merged component
# ---------------------------------------------------------------------------
class TestKnowledgeComponentShape:
    def test_mode_input_exists_with_expected_options(self) -> None:
        component = KnowledgeComponent()
        options = _mode_options(component)
        assert options == [MODE_INGEST, MODE_RETRIEVE]

    def test_default_mode_is_ingest(self) -> None:
        component = KnowledgeComponent()
        mode_input = next(i for i in component.inputs if i.name == "mode")
        assert mode_input.value == MODE_INGEST

    def test_mode_config_partition_covers_only_known_fields(self) -> None:
        """Each mode lists its fields exactly once; defaults never appear in either bucket.

        ``mode_config`` must list every mode-specific field exactly once
        and never list any of the ``default_keys`` that are always shown.
        """
        component = KnowledgeComponent()
        all_input_names = {i.name for i in component.inputs}
        partitioned = set(component.mode_config[MODE_INGEST]) | set(component.mode_config[MODE_RETRIEVE])
        # No overlap between the two mode buckets.
        assert not set(component.mode_config[MODE_INGEST]) & set(component.mode_config[MODE_RETRIEVE])
        # No mode bucket lists a default-key field.
        assert not partitioned & set(component.default_keys)
        # Every name in the buckets is a real declared input.
        assert partitioned <= all_input_names

    def test_default_keys_are_always_present(self) -> None:
        component = KnowledgeComponent()
        all_input_names = {i.name for i in component.inputs}
        assert set(component.default_keys) <= all_input_names
        assert "mode" in component.default_keys
        assert "knowledge_base" in component.default_keys


# ---------------------------------------------------------------------------
# update_build_config — input visibility toggling
# ---------------------------------------------------------------------------
class TestModeDrivenInputVisibility:
    @pytest.fixture(autouse=True)
    def _skip_astra_gate(self):
        """Stub the astra-cloud gate so update_build_config can proceed in tests.

        ``update_build_config`` calls the astra-cloud gate as its first
        action — in tests we just need it to be a no-op.
        """
        with patch("lfx.components.files_and_knowledge.knowledge.raise_error_if_astra_cloud_disable_component") as gate:
            gate.return_value = None
            yield

    async def test_switching_to_retrieve_hides_ingest_fields(self) -> None:
        component = KnowledgeComponent()
        build_config = _build_config_from_inputs(component)
        build_config["mode"]["value"] = MODE_INGEST

        updated = await component.update_build_config(build_config, MODE_RETRIEVE, "mode")

        for fname in component.mode_config[MODE_INGEST]:
            assert updated[fname]["show"] is False, f"{fname} should be hidden in retrieve mode"
        for fname in component.mode_config[MODE_RETRIEVE]:
            assert updated[fname]["show"] is True, f"{fname} should be visible in retrieve mode"
        # Default keys remain visible regardless of mode.
        for fname in component.default_keys:
            assert updated[fname]["show"] is True

    async def test_switching_to_ingest_hides_retrieve_fields(self) -> None:
        component = KnowledgeComponent()
        build_config = _build_config_from_inputs(component)
        # Start the build_config in retrieve mode so we can observe the flip.
        build_config["mode"]["value"] = MODE_RETRIEVE
        for fname in component.mode_config[MODE_INGEST]:
            build_config[fname]["show"] = False
        for fname in component.mode_config[MODE_RETRIEVE]:
            build_config[fname]["show"] = True

        updated = await component.update_build_config(build_config, MODE_INGEST, "mode")

        for fname in component.mode_config[MODE_INGEST]:
            assert updated[fname]["show"] is True, f"{fname} should be visible in ingest mode"
        for fname in component.mode_config[MODE_RETRIEVE]:
            assert updated[fname]["show"] is False, f"{fname} should be hidden in ingest mode"

    async def test_unknown_mode_falls_back_to_ingest_visibility(self) -> None:
        """Stale flows may carry an unknown mode value — fall back gracefully."""
        component = KnowledgeComponent()
        build_config = _build_config_from_inputs(component)
        build_config["mode"]["value"] = "bogus-mode-value"

        # field_name=None mirrors an initial node render with no triggering field.
        updated = await component.update_build_config(build_config, None, None)

        for fname in component.mode_config[MODE_INGEST]:
            assert updated[fname]["show"] is True
        for fname in component.mode_config[MODE_RETRIEVE]:
            assert updated[fname]["show"] is False


# ---------------------------------------------------------------------------
# Class-level outputs + update_outputs filtering
# ---------------------------------------------------------------------------
class TestModeDrivenOutputSwap:
    def test_class_level_declares_both_outputs_for_runtime_dispatch(self) -> None:
        """Both output methods are declared at the class level so the runtime can dispatch correctly.

        Without this, the runtime falls back to the only declared output and
        crashes when the wrong-mode method runs against missing inputs (e.g.
        ``build_kb_info`` calling ``convert_to_dataframe(None)`` in retrieve
        mode).
        """
        output_names = {o.name for o in KnowledgeComponent.outputs}
        assert output_names == {"dataframe_output", "retrieve_data"}
        method_names = {o.method for o in KnowledgeComponent.outputs}
        assert method_names == {"build_kb_info", "retrieve_data"}

    def test_retrieve_mode_replaces_output_with_retrieve_result(self) -> None:
        component = KnowledgeComponent()
        frontend_node: dict = {"outputs": list(component.outputs)}

        result = component.update_outputs(frontend_node, "mode", MODE_RETRIEVE)

        assert len(result["outputs"]) == 1
        out = result["outputs"][0]
        # Legacy output name preserved so saved flow edges keyed on
        # ``retrieve_data`` continue to resolve.
        assert out.name == "retrieve_data"
        assert out.method == "retrieve_data"

    def test_ingest_mode_replaces_output_with_ingest_result(self) -> None:
        component = KnowledgeComponent()
        # Pretend we were previously in retrieve mode.
        frontend_node: dict = {
            "outputs": [
                {"name": "retrieve_data", "method": "retrieve_data", "display_name": "Results"},
            ]
        }

        result = component.update_outputs(frontend_node, "mode", MODE_INGEST)

        assert len(result["outputs"]) == 1
        out = result["outputs"][0]
        # Legacy output name preserved so saved flow edges keyed on
        # ``dataframe_output`` continue to resolve.
        assert out.name == "dataframe_output"
        assert out.method == "build_kb_info"

    def test_non_mode_field_change_leaves_outputs_untouched(self) -> None:
        component = KnowledgeComponent()
        original = [{"name": "dataframe_output", "method": "build_kb_info"}]
        frontend_node: dict = {"outputs": list(original)}

        result = component.update_outputs(frontend_node, "top_k", 10)

        assert result["outputs"] == original


# ---------------------------------------------------------------------------
# Output-method mode dispatch (stale edges + legacy labels)
# ---------------------------------------------------------------------------
class TestOutputMethodModeDispatch:
    """Output methods dispatch by mode so saved flows survive edge staleness.

    If a user wires the ingest output, then switches to retrieve mode, the
    saved edge still references ``build_kb_info``. Without dispatch, the
    runtime would call the wrong method against the (now-None) ingest
    inputs and crash with ``NoneType.to_dataframe``.
    """

    def test_is_retrieve_mode_matches_canonical_and_legacy_labels(self) -> None:
        assert _is_retrieve_mode(MODE_RETRIEVE) is True
        # Legacy emoji label from the original PR version of this component
        # — saved flows may still carry it.
        assert _is_retrieve_mode("🔍 Retrieve") is True
        assert _is_retrieve_mode(MODE_INGEST) is False
        assert _is_retrieve_mode("📥 Ingest") is False
        assert _is_retrieve_mode(None) is False
        assert _is_retrieve_mode(42) is False

    async def test_build_kb_info_delegates_to_retrieve_when_mode_is_retrieve(self) -> None:
        """Stale-edge safety net: wiring the ingest output should not crash a retrieve flow."""
        component = KnowledgeComponent()
        component.mode = MODE_RETRIEVE
        sentinel = object()
        component.retrieve_data = AsyncMock(return_value=sentinel)

        result = await component.build_kb_info()

        assert result is sentinel
        component.retrieve_data.assert_awaited_once()

    async def test_retrieve_data_delegates_to_ingest_when_mode_is_ingest(self) -> None:
        """Symmetric safety net for the inverse stale-edge case."""
        component = KnowledgeComponent()
        component.mode = MODE_INGEST
        sentinel = object()
        component.build_kb_info = AsyncMock(return_value=sentinel)

        result = await component.retrieve_data()

        assert result is sentinel
        component.build_kb_info.assert_awaited_once()


# ---------------------------------------------------------------------------
# Subclass shims — backward-compat
# ---------------------------------------------------------------------------
class TestLegacySubclassesPinMode:
    def test_ingestion_subclass_pins_ingest_mode(self) -> None:
        component = KnowledgeIngestionComponent()
        assert component.mode == MODE_INGEST
        assert component.name == "KnowledgeIngestion"
        assert component.display_name == "Knowledge Ingestion"

    def test_retrieval_subclass_pins_retrieve_mode(self) -> None:
        component = KnowledgeBaseComponent()
        assert component.mode == MODE_RETRIEVE
        assert component.name == "KnowledgeBase"
        assert component.display_name == "Knowledge Base"

    def test_subclasses_inherit_merged_inputs(self) -> None:
        """Saved legacy flows must keep loading against either subclass.

        Both subclasses must declare the full superset of inputs so that
        saved legacy flows (which reference field names like ``input_df`` /
        ``top_k``) continue to load against either class.
        """
        ingest_input_names = {i.name for i in KnowledgeIngestionComponent.inputs}
        retrieve_input_names = {i.name for i in KnowledgeBaseComponent.inputs}
        for name in ("input_df", "top_k", "knowledge_base", "mode"):
            assert name in ingest_input_names, f"KnowledgeIngestionComponent missing input: {name}"
            assert name in retrieve_input_names, f"KnowledgeBaseComponent missing input: {name}"

    def test_retrieval_module_reexports_filter_helpers(self) -> None:
        """Back-compat re-export keeps legacy test imports working.

        ``test_retrieval.py`` imports these helpers from the retrieval
        module — the back-compat re-export must keep that working.
        """
        from lfx.components.files_and_knowledge.retrieval import (
            _chunk_matches_filter,
            _parse_metadata_filter,
        )

        assert _parse_metadata_filter(None) == {}
        assert _chunk_matches_filter(None, {}) is True
