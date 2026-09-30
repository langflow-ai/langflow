"""Unit tests for the shared flow-envelope helpers (lfx.utils.flow_envelope).

These back the outer-envelope handling used by `lfx run`, `lfx serve`, `lfx upgrade`, and the
graph loader, so they're the single place the unwrap/rewrap rules are pinned.
"""

import pytest
from lfx.utils.flow_envelope import merge_flow_envelope, split_flow_envelope

BARE = {"nodes": [{"id": "n1"}], "edges": []}


class TestSplitFlowEnvelope:
    def test_enveloped_payload_split(self):
        env = {"name": "F", "description": "d", "data": BARE}
        outer, inner = split_flow_envelope(env)
        assert outer == env
        assert inner == BARE

    def test_bare_payload_passthrough(self):
        outer, inner = split_flow_envelope(BARE)
        assert outer is None
        assert inner == BARE

    def test_data_present_but_not_a_dict_is_treated_as_bare(self):
        # {"data": <non-dict>} is not the exported-flow shape; don't unwrap into a non-graph.
        payload = {"data": "not-a-graph", "nodes": []}
        outer, inner = split_flow_envelope(payload)
        assert outer is None
        assert inner == payload

    def test_nested_envelope_unwraps_one_level(self):
        outer, inner = split_flow_envelope({"data": {"data": BARE}})
        assert outer == {"data": {"data": BARE}}
        assert inner == {"data": BARE}

    def test_empty_dict_is_bare(self):
        outer, inner = split_flow_envelope({})
        assert outer is None
        assert inner == {}

    @pytest.mark.parametrize("bad", [[], "x", 5, None, ("a",)])
    def test_non_dict_raises_typeerror(self, bad):
        with pytest.raises(TypeError, match="must be a JSON object"):
            split_flow_envelope(bad)


class TestMergeFlowEnvelope:
    def test_enveloped_preserves_metadata_and_swaps_inner(self):
        outer = {"name": "F", "description": "d", "data": {"old": True}}
        new_inner = {"nodes": [1], "edges": []}
        result = merge_flow_envelope(outer, new_inner, wrap_bare=True)
        assert result == {"name": "F", "description": "d", "data": new_inner}

    def test_enveloped_ignores_wrap_bare_flag(self):
        outer = {"name": "F", "data": {}}
        for wrap_bare in (True, False):
            assert merge_flow_envelope(outer, BARE, wrap_bare=wrap_bare) == {"name": "F", "data": BARE}

    def test_bare_wrapped_for_loader(self):
        # wrap_bare=True: the loader needs the {"data": ...} envelope.
        assert merge_flow_envelope(None, BARE, wrap_bare=True) == {"data": BARE}

    def test_bare_kept_flat_for_write(self):
        # wrap_bare=False: --write preserves the flat on-disk shape.
        assert merge_flow_envelope(None, BARE, wrap_bare=False) == BARE

    def test_split_then_merge_roundtrips_enveloped(self):
        env = {"name": "F", "data": BARE}
        outer, inner = split_flow_envelope(env)
        assert merge_flow_envelope(outer, inner, wrap_bare=True) == env

    def test_split_then_merge_roundtrips_bare_for_write(self):
        outer, inner = split_flow_envelope(BARE)
        assert merge_flow_envelope(outer, inner, wrap_bare=False) == BARE
