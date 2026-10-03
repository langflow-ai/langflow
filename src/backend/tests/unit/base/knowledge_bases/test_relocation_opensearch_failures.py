"""OpenSearch read errors cannot turn an empty relocation into a successful move."""

from unittest.mock import MagicMock

from langflow.api.utils import knowledge_base_relocation, knowledge_base_service
from langflow.services.deps import get_settings_service
from lfx.base.knowledge_bases.backends import OpenSearchBackend


async def test_empty_sqlite_kb_is_not_repointed_to_an_unreachable_opensearch(active_user, tmp_path, monkeypatch):
    root = tmp_path / "knowledge_bases"
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(root))
    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name="empty_kb_unreachable_target", chunks=0
    )
    target = OpenSearchBackend(kb_name=record.name, user_id=record.user_id)
    target._secrets_resolved = True
    target._os_client = MagicMock()
    target._os_client.indices.get_mapping.return_value = {
        "test_index": {
            "mappings": {"properties": {"vector_field": {"type": "knn_vector", "method": {"space_type": "l2"}}}}
        }
    }
    target._os_client.count.side_effect = OSError("remote unavailable")
    target._os_index = "test_index"
    monkeypatch.setattr(knowledge_base_relocation, "_build_backend", lambda *_args: target)

    results = await knowledge_base_relocation.relocate_knowledge_bases(
        target_backend_type="opensearch", target_backend_config={}
    )

    result = next(result for result in results if result.kb_id == record.id)
    assert result.status == "failed"
    assert "remote unavailable" in result.reason
    row = await knowledge_base_service.get_by_id(record.id)
    assert row.backend_type == "sqlite"
    assert row.backend_config == record.backend_config
    assert row.storage_generation == record.storage_generation
