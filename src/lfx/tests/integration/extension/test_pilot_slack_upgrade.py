"""Integration test: legacy slack flows upgrade cleanly.

Mirrors ``test_pilot_paddle_upgrade.py`` for the seven ``lfx-slack``
components. ``lfx-slack`` never shipped in-tree, so the bare-name and
import-path forms exist only so a flow authored against a pre-release build (or
hand-edited) still resolves; the ``@official-pre-a`` slot form is the one that
matters for saved flows.
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"

COMPONENT_CLASSES = (
    "SlackSearchComponent",
    "SlackReadThreadComponent",
    "SlackSendAsUserComponent",
    "SlackCanvasComponent",
    "SlackPostAsAppComponent",
    "SlackAddReactionComponent",
    "SlackListChannelMembersComponent",
)
MODULE_BY_CLASS = {
    "SlackSearchComponent": "slack_search",
    "SlackReadThreadComponent": "slack_read_thread",
    "SlackSendAsUserComponent": "slack_send_as_user",
    "SlackCanvasComponent": "slack_canvas",
    "SlackPostAsAppComponent": "slack_post_as_app",
    "SlackAddReactionComponent": "slack_add_reaction",
    "SlackListChannelMembersComponent": "slack_list_channel_members",
}


@pytest.fixture(scope="module")
def migration_table():
    table, error = load_migration_table(TABLE_PATH)
    assert error is None, f"failed to load migration table: {error}"
    assert table is not None
    return table


def _saved_flow_node(node_id: str, type_value: str) -> dict:
    """Build a minimal saved-flow node skeleton for testing."""
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {"id": node_id, "type": type_value, "node": {"template": {}}},
    }


def _saved_flow(*nodes: dict) -> dict:
    return {"data": {"nodes": list(nodes), "edges": []}}


@pytest.mark.integration
@pytest.mark.parametrize("class_name", COMPONENT_CLASSES)
def test_legacy_bare_name_flow_upgrades(migration_table, class_name: str) -> None:
    """Pre-Phase-A flow with the bare class name upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("slack-1", class_name))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == f"ext:slack:{class_name}@official"
    [record] = report.records
    assert record.legacy_form_kind == "bare_class_name"


@pytest.mark.integration
@pytest.mark.parametrize("class_name", COMPONENT_CLASSES)
def test_legacy_import_path_flow_upgrades(migration_table, class_name: str) -> None:
    """Dotted and package-level import-path forms upgrade to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    module = MODULE_BY_CLASS[class_name]
    flow = _saved_flow(
        _saved_flow_node("slack-2", f"lfx.components.slack.{module}.{class_name}"),
        _saved_flow_node("slack-3", f"lfx.components.slack.{class_name}"),
    )
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 2
    expected = f"ext:slack:{class_name}@official"
    assert [node["data"]["type"] for node in flow["data"]["nodes"]] == [expected, expected]
    assert {record.legacy_form_kind for record in report.records} == {"import_path"}


@pytest.mark.integration
@pytest.mark.parametrize("class_name", COMPONENT_CLASSES)
def test_legacy_slot_flow_upgrades(migration_table, class_name: str) -> None:
    """The pre-Phase-A ``@official-pre-a`` slot form upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("slack-4", f"ext:slack:{class_name}@official-pre-a"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == f"ext:slack:{class_name}@official"
    assert report.records[0].legacy_form_kind == "legacy_slot"


@pytest.mark.integration
def test_lfx_slack_distribution_is_importable() -> None:
    """The bundle's package is importable in the development workspace."""
    try:
        import lfx_slack
    except ImportError:
        pytest.skip("lfx-slack not installed in this test environment")

    for class_name in COMPONENT_CLASSES:
        assert getattr(lfx_slack, class_name).__name__ == class_name


def _is_editable_install(dist: importlib_metadata.Distribution) -> bool:
    direct_url = dist.read_text("direct_url.json")
    if not direct_url:
        return False
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError:
        return False
    return bool(payload.get("dir_info", {}).get("editable"))


@pytest.mark.integration
def test_lfx_slack_ships_manifest_and_capabilities() -> None:
    """``importlib.metadata`` finds both JSON documents for the installed dist."""
    try:
        dist = importlib_metadata.distribution("lfx-slack")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-slack not installed in this test environment")

    if _is_editable_install(dist):
        import lfx_slack

        package_dir = Path(lfx_slack.__file__).parent
        manifest_path = package_dir / "extension.json"
        assert manifest_path.is_file()
    else:
        files = dist.files or []
        manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
        assert manifests
        manifest_path = Path(dist.locate_file(manifests[0]))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-slack"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(bundle["name"] == "slack" for bundle in manifest["bundles"])
    [integration] = manifest["integrations"]
    assert integration["provider_id"] == "slack"
    assert (manifest_path.parent / "components" / "slack" / integration["path"]).is_file()
