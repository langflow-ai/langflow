"""Runtime checks migrate detached legacy identities without changing stored nodes."""

from copy import deepcopy

import pytest
from langflow.upgrade_check import engine
from langflow.upgrade_check.engine import Target, TargetSettings
from lfx.services.catalog_policy import CatalogPolicySnapshot
from lfx.utils.flow_validation import _compute_code_hash

CURRENT = "ext:openai:OpenAIModelComponent@official"
LEGACY = "ext:openai:OpenAIModelComponent@official-pre-a"
TEMPLATE = {
    "display_name": "Fixture",
    "template": {"code": {"type": "code", "value": "class Fixture:\n    pass\n"}},
    "metadata": {"code_hash": _compute_code_hash("class Fixture:\n    pass\n")},
}


def _saved_node():
    return {"id": "Fixture-1", "data": {"type": LEGACY, "node": deepcopy(TEMPLATE)}}


@pytest.mark.parametrize(
    "settings", [TargetSettings(allow_custom_components=False), TargetSettings(custom_component_admin_only=True)]
)
def test_legacy_slot_runs_installed_server_code_without_changing_saved_node(settings):
    node = _saved_node()
    before = deepcopy(node)
    target = Target.from_registry({"fixture": {CURRENT: deepcopy(TEMPLATE)}}, settings)

    runs, refusal = engine._runs(node, target, is_superuser=False)

    assert (runs, refusal) == ("server_code", None)
    assert node == before


@pytest.mark.parametrize("blocked", [LEGACY, CURRENT])
def test_original_and_migrated_catalog_identity_denials_remain_refused(blocked):
    node = _saved_node()
    before = deepcopy(node)
    target = Target.from_registry(
        {"fixture": {CURRENT: deepcopy(TEMPLATE)}},
        TargetSettings(allow_custom_components=False),
        CatalogPolicySnapshot(blocked_component_keys=frozenset({blocked})),
    )

    runs, refusal = engine._runs(node, target, is_superuser=False)

    assert runs == "refused"
    assert refusal["code"] == "refused"
    assert "catalog policy blocks" in refusal["message"]
    assert node == before


def test_legacy_migration_does_not_allow_an_uninstalled_target():
    target = Target.from_registry({}, TargetSettings(allow_custom_components=False))
    runs, refusal = engine._runs(_saved_node(), target, is_superuser=False)
    assert runs == "refused"
    assert refusal is not None
