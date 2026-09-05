"""The shipped components carry the input and output names the INT-1 matrix froze.

``scripts/ci/check_capability_manifests.py`` proves the capability manifest and
``design/dedicated-integrations/matrices/slack.json`` agree on ids, identity,
scopes, contexts and component_ref. It cannot compare field names, because the
manifest carries no schema -- only the matrix does. Without this test the four
deliberate deviations below would be indistinguishable from an accidental
rename, and a fifth could appear unnoticed.

Every deviation is listed explicitly and the list is asserted exhaustive, so
removing one (by amending the matrix, say) fails here until this file is
updated too.
"""

from __future__ import annotations

import json
from pathlib import Path

import lfx_slack
import pytest
from lfx.inputs.inputs import ConnectionRefInput

MATRIX_PATH = Path(__file__).resolve().parents[4] / "design" / "dedicated-integrations" / "matrices" / "slack.json"
MANIFEST_PATH = Path(lfx_slack.__file__).parent / "components" / "slack" / "capabilities.v1.json"

# action_id -> (matrix name, shipped name), with the reason the two differ.
INPUT_DEVIATIONS = {
    # ``Component.name`` is the registry-name override, so an input called
    # ``name`` is silently shadowed by the class attribute: ``self.name`` would
    # return the component's own name with no error. The Web API parameter is
    # still sent as ``name``; only the component-side field is renamed.
    "slack.bot.add_reaction": {("name", "emoji_name")},
}

# action_id -> (frozen matrix output names, single shipped output name).
# Langflow edges are typed, so a bare ``bool``/``str`` output cannot be consumed
# downstream; each group of scalars ships as one Data output carrying the same
# keys, which the recorded-fixture tests assert.
OUTPUT_DEVIATIONS = {
    "slack.user.read_thread": (("has_more", "next_cursor"), "pagination"),
    "slack.user.canvas": (("canvas_id",), "canvas"),
    "slack.bot.list_channel_members": (("next_cursor",), "pagination"),
}


def _matrix_rows() -> dict[str, dict]:
    if not MATRIX_PATH.is_file():  # installed-wheel runs have no design/ tree
        pytest.skip(f"capability matrix not available at {MATRIX_PATH}")
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return {action["action_id"]: action for action in matrix["actions"] if action["decision"] == "include"}


def _capabilities() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["capabilities"]


def test_component_inputs_match_the_frozen_matrix() -> None:
    rows = _matrix_rows()
    unused = dict(INPUT_DEVIATIONS)
    for capability in _capabilities():
        component_class = getattr(lfx_slack, capability["component_ref"])
        shipped = {i.name for i in component_class.inputs if not isinstance(i, ConnectionRefInput)}
        expected = {i["name"] for i in rows[capability["id"]]["schema"]["inputs"]}
        for matrix_name, shipped_name in unused.pop(capability["id"], set()):
            assert matrix_name in expected, f"{capability['id']}: matrix no longer declares {matrix_name!r}"
            assert shipped_name in shipped, f"{capability['id']}: {shipped_name!r} is gone; drop the deviation"
            expected = (expected - {matrix_name}) | {shipped_name}
        assert shipped == expected, capability["id"]
    assert not unused, f"stale input deviations: {sorted(unused)}"


def test_component_outputs_match_the_frozen_matrix() -> None:
    rows = _matrix_rows()
    unused = dict(OUTPUT_DEVIATIONS)
    for capability in _capabilities():
        component_class = getattr(lfx_slack, capability["component_ref"])
        shipped = {output.name for output in component_class.outputs}
        expected = {o["name"] for o in rows[capability["id"]]["schema"]["outputs"]}
        folded = unused.pop(capability["id"], None)
        if folded is not None:
            matrix_names, shipped_name = folded
            assert set(matrix_names) <= expected, f"{capability['id']}: matrix changed under the deviation"
            assert shipped_name in shipped, f"{capability['id']}: {shipped_name!r} is gone; drop the deviation"
            expected = (expected - set(matrix_names)) | {shipped_name}
        assert shipped == expected, capability["id"]
    assert not unused, f"stale output deviations: {sorted(unused)}"
