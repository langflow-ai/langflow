"""Security tests for file references injected into ChatInput builds."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.services.storage.local import LocalStorageService
from lfx.utils.file_path_security import LocalFileAccessError


def _make_services(config_dir, *, restricted: bool, storage_type: str = "local"):
    settings_service = MagicMock()
    settings_service.settings.config_dir = str(config_dir)
    settings_service.settings.database_url = ""
    settings_service.settings.restrict_local_file_access = restricted
    settings_service.settings.storage_type = storage_type
    storage_service = LocalStorageService(MagicMock(), settings_service)
    return settings_service, storage_service


def _make_chat_input(*, files: list[str], flow_id: str, user_id: str) -> ChatInput:
    component = ChatInput()
    component.build(
        files=files,
        input_value="inspect attachment",
        should_store_message=False,
    )
    # Provide the same execution scopes graph initialization assigns in production.
    component._vertex = SimpleNamespace(graph=SimpleNamespace(flow_id=flow_id, session_id="", user_id=user_id))
    component._user_id = user_id
    return component


def _make_graph(*, flow_id: str, user_id: str) -> Graph:
    chat_input = ChatInput(_id="chat-input", should_store_message=False)
    chat_output = ChatOutput(_id="chat-output", should_store_message=False)
    chat_output.set(input_value=chat_input.message_response)
    return Graph(chat_input, chat_output, flow_id=flow_id, user_id=user_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file_reference",
    [
        "{external_file}",
        "flow-id/../server-secret.txt",
    ],
)
async def test_chat_input_rejects_external_local_file_references(tmp_path, file_reference):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    external_file = tmp_path / "server-secret.txt"
    external_file.write_text("do-not-exfiltrate", encoding="utf-8")
    reference = file_reference.format(external_file=external_file)
    settings_service, storage_service = _make_services(config_dir, restricted=True)
    graph = _make_graph(flow_id="flow-id", user_id="user-id")

    with (
        patch("lfx.components.input_output.chat.get_settings_service", return_value=settings_service),
        patch("lfx.schema.image.get_storage_service", return_value=storage_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
        pytest.raises(LocalFileAccessError),
    ):
        await graph.astep(files=[reference], user_id="user-id")


@pytest.mark.asyncio
async def test_chat_input_rejects_external_file_when_unsupported_storage_falls_back_to_local(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    external_file = tmp_path / "server-secret.txt"
    external_file.write_text("do-not-exfiltrate", encoding="utf-8")
    settings_service, storage_service = _make_services(
        config_dir,
        restricted=True,
        storage_type="unsupported-storage",
    )
    assert isinstance(storage_service, LocalStorageService)
    graph = _make_graph(flow_id="flow-id", user_id="user-id")

    with (
        patch("lfx.components.input_output.chat.get_settings_service", return_value=settings_service),
        patch("lfx.schema.image.get_storage_service", return_value=storage_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
        pytest.raises(LocalFileAccessError),
    ):
        await graph.astep(files=[str(external_file)], user_id="user-id")


@pytest.mark.asyncio
@pytest.mark.parametrize("scope_id", ["flow-id", "user-id"])
async def test_chat_input_keeps_valid_stored_file_references(tmp_path, scope_id):
    config_dir = tmp_path / "config"
    stored_file = config_dir / scope_id / "upload.txt"
    stored_file.parent.mkdir(parents=True)
    stored_file.write_text("safe attachment", encoding="utf-8")
    reference = f"{scope_id}/{stored_file.name}"
    settings_service, storage_service = _make_services(config_dir, restricted=True)
    component = _make_chat_input(files=[reference], flow_id="flow-id", user_id="user-id")

    with (
        patch("lfx.components.input_output.chat.get_settings_service", return_value=settings_service),
        patch("lfx.schema.image.get_storage_service", return_value=storage_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
    ):
        message = await component.message_response()
        content_dicts = message.get_file_content_dicts()

    assert message.files == [reference]
    assert content_dicts == [{"type": "text", "text": "File 'upload.txt' contents:\nsafe attachment"}]


@pytest.mark.asyncio
async def test_chat_input_keeps_server_provenance_public_file_reference(tmp_path):
    config_dir = tmp_path / "config"
    source_flow_id = "source-flow"
    stored_file = config_dir / source_flow_id / "public-upload.txt"
    stored_file.parent.mkdir(parents=True)
    stored_file.write_text("public attachment", encoding="utf-8")
    settings_service, storage_service = _make_services(config_dir, restricted=True)
    graph = _make_graph(flow_id="visitor-virtual-flow", user_id="owner-user")
    # generate_flow_events assigns this only from its server-supplied source_flow_id.
    graph.source_flow_id = source_flow_id

    with (
        patch("lfx.components.input_output.chat.get_settings_service", return_value=settings_service),
        patch("lfx.schema.image.get_storage_service", return_value=storage_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
    ):
        build_result = await graph.astep(files=[f"{source_flow_id}/{stored_file.name}"], user_id="owner-user")
        message = build_result.vertex.results["message"]
        content_dicts = message.get_file_content_dicts()

    assert content_dicts == [{"type": "text", "text": "File 'public-upload.txt' contents:\npublic attachment"}]


@pytest.mark.asyncio
async def test_chat_input_keeps_public_file_reference_in_subgraph(tmp_path):
    config_dir = tmp_path / "config"
    source_flow_id = "source-flow"
    stored_file = config_dir / source_flow_id / "public-upload.txt"
    stored_file.parent.mkdir(parents=True)
    stored_file.write_text("public attachment", encoding="utf-8")
    settings_service, storage_service = _make_services(config_dir, restricted=True)
    graph = _make_graph(flow_id="visitor-virtual-flow", user_id="owner-user")
    graph.source_flow_id = source_flow_id

    with (
        patch("lfx.components.input_output.chat.get_settings_service", return_value=settings_service),
        patch("lfx.schema.image.get_storage_service", return_value=storage_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
    ):
        async with graph.create_subgraph({"chat-input", "chat-output"}) as subgraph:
            assert subgraph.source_flow_id == source_flow_id
            subgraph.prepare()
            build_result = await subgraph.astep(
                files=[f"{source_flow_id}/{stored_file.name}"],
                user_id="owner-user",
            )
            message = build_result.vertex.results["message"]
            content_dicts = message.get_file_content_dicts()

    assert content_dicts == [{"type": "text", "text": "File 'public-upload.txt' contents:\npublic attachment"}]


@pytest.mark.asyncio
async def test_chat_input_rejects_untrusted_public_source_scope(tmp_path):
    config_dir = tmp_path / "config"
    source_flow_id = "untrusted-source-flow"
    stored_file = config_dir / source_flow_id / "public-upload.txt"
    stored_file.parent.mkdir(parents=True)
    stored_file.write_text("must stay private", encoding="utf-8")
    settings_service, storage_service = _make_services(config_dir, restricted=True)
    graph = _make_graph(flow_id="visitor-virtual-flow", user_id="owner-user")
    # Request-derived graph context is not trusted storage provenance.
    graph.context["source_flow_id"] = source_flow_id

    with (
        patch("lfx.components.input_output.chat.get_settings_service", return_value=settings_service),
        patch("lfx.schema.image.get_storage_service", return_value=storage_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
        pytest.raises(LocalFileAccessError),
    ):
        await graph.astep(files=[f"{source_flow_id}/{stored_file.name}"], user_id="owner-user")

    assert graph.source_flow_id is None


@pytest.mark.asyncio
async def test_chat_input_keeps_unrestricted_local_file_compatibility(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    external_file = tmp_path / "local-input.txt"
    external_file.write_text("single-tenant input", encoding="utf-8")
    settings_service, storage_service = _make_services(config_dir, restricted=False)
    component = _make_chat_input(files=[str(external_file)], flow_id="flow-id", user_id="user-id")

    with (
        patch("lfx.components.input_output.chat.get_settings_service", return_value=settings_service),
        patch("lfx.schema.image.get_storage_service", return_value=storage_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
    ):
        message = await component.message_response()
        content_dicts = message.get_file_content_dicts()

    assert message.files == [str(external_file)]
    assert content_dicts == [{"type": "text", "text": "File 'local-input.txt' contents:\nsingle-tenant input"}]
