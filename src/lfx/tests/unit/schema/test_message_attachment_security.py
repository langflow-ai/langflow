"""Stored chat attachments must never turn model input into an unrestricted file read."""

import asyncio
import base64
from types import SimpleNamespace

import pytest
from lfx.base.data.storage_utils import get_file_size, read_file_bytes, read_file_text
from lfx.schema.message import Message
from lfx.utils.file_path_security import LocalFileAccessError, StorageNamespaceError, file_access_scope


@pytest.fixture
def attachment_layout(tmp_path, monkeypatch):
    """Create harmless owned, foreign, outside, and reserved local attachment canaries."""
    from lfx.services.deps import get_settings_service
    from lfx.utils.image import create_image_content_dict

    storage = tmp_path / "storage"
    (storage / "flow-id").mkdir(parents=True)
    (storage / "user-id").mkdir()
    (storage / "other-user").mkdir()
    owned = storage / "user-id" / "upload.txt"
    owned.write_text("allowed attachment canary")
    foreign = storage / "other-user" / "upload.txt"
    foreign.write_text("foreign attachment canary")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside attachment canary")
    reserved = storage / "secret_key"
    reserved.write_text("reserved attachment canary")
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "local")
    monkeypatch.setattr(settings, "restrict_local_file_access", True)
    monkeypatch.setattr(settings, "config_dir", str(storage))
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr("lfx.schema.image.get_storage_service", lambda: None)
    monkeypatch.setattr("lfx.utils.image.get_storage_service", lambda: None)
    create_image_content_dict.cache_clear()
    return SimpleNamespace(storage=storage, owned=owned, foreign=foreign, outside=outside, reserved=reserved)


@pytest.mark.parametrize("target", ["outside", "reserved"])
def test_stored_message_attachment_does_not_disclose_server_file(attachment_layout, target):
    """Keep turn text while excluding outside or server-managed file contents."""
    path = getattr(attachment_layout, target)
    message = Message(text="keep this turn", sender="User", files=[str(path)])

    assert message.to_lc_message().content == [{"type": "text", "text": "keep this turn"}]


def test_graph_scope_denies_other_uploads_and_keeps_own_attachment(attachment_layout):
    """Read owned uploads without including another user's stored attachment."""
    message = Message(
        text="keep this turn", sender="User", files=[str(attachment_layout.foreign), str(attachment_layout.owned)]
    )
    with file_access_scope(("user-id", "flow-id")):
        content = message.to_lc_message().content

    assert len(content) == 2
    assert "allowed attachment canary" in content[1]["text"]
    assert "foreign attachment canary" not in str(content)


def test_symlink_attachment_cannot_escape_graph_scope(attachment_layout):
    """Resolve symlinks before allowing a scoped attachment read."""
    link = attachment_layout.storage / "flow-id" / "alias.txt"
    link.symlink_to(attachment_layout.outside)
    with file_access_scope(("user-id", "flow-id")):
        assert Message(text="turn", files=[str(link)]).get_file_content_dicts() == []


def test_image_attachment_is_checked_before_conversion(attachment_layout):
    """Exclude outside images from model-content conversion."""
    image = attachment_layout.outside.with_suffix(".png")
    image.write_bytes(
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==")
    )
    assert Message(text="turn", files=[str(image)]).get_file_content_dicts() == []


@pytest.mark.parametrize("inside_scope", [False, True])
def test_s3_service_unavailable_never_falls_back_to_local_image(attachment_layout, monkeypatch, inside_scope):
    """Skip images when S3 is unavailable even if a corresponding local file exists."""
    from lfx.services.deps import get_settings_service

    path = attachment_layout.owned if inside_scope else attachment_layout.outside
    image = path.with_suffix(".png")
    image.write_bytes(
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==")
    )
    monkeypatch.setattr(get_settings_service().settings, "storage_type", "s3")
    monkeypatch.setattr("lfx.services.deps.get_storage_service", lambda: None)
    with file_access_scope(("user-id",)):
        assert Message(text="turn", files=[str(image)]).get_file_content_dicts() == []


def test_scoped_local_image_attachment_remains_readable(attachment_layout):
    """Preserve image encoding for a local upload inside the trusted user scope."""
    image = attachment_layout.owned.with_suffix(".png")
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    image.write_bytes(png)
    with file_access_scope(("user-id",)):
        content = Message(text="turn", files=[str(image)]).get_file_content_dicts()

    assert content[0]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(png).decode()


@pytest.fixture
def scoped_object_storage(attachment_layout, monkeypatch):
    """Provide observable object reads with user, flow, and public source-flow keys."""
    from unittest.mock import AsyncMock

    from lfx.services.deps import get_settings_service

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    storage = SimpleNamespace(
        data_dir=attachment_layout.storage,
        parse_file_path=lambda path: tuple(path.removeprefix("files/").rsplit("/", 1)),
        build_full_path=lambda flow_id, file_name: f"files/{flow_id}/{file_name}",
        get_file=AsyncMock(
            side_effect=lambda flow_id, file_name: (
                png if file_name.endswith(".png") else f"object upload canary {flow_id}".encode()
            )
        ),
        get_file_size=AsyncMock(return_value=20),
    )
    monkeypatch.setattr(get_settings_service().settings, "storage_type", "s3")
    monkeypatch.setattr("lfx.services.deps.get_storage_service", lambda: storage)
    monkeypatch.setattr("lfx.schema.image.get_storage_service", lambda: storage)
    monkeypatch.setattr("lfx.utils.image.get_storage_service", lambda: storage)
    monkeypatch.setattr("lfx.base.data.storage_utils.get_storage_service", lambda: storage)
    return storage


@pytest.mark.parametrize("extension", ["png", "txt"])
def test_s3_foreign_attachment_is_rejected_before_object_read(scoped_object_storage, extension):
    """Reject foreign S3 images and text before reading bytes or object metadata."""
    with file_access_scope(("user-id", "flow-id", "source-flow")):
        content = Message(text="turn", files=[f"foreign-user/upload.{extension}"]).get_file_content_dicts()

    assert content == []
    scoped_object_storage.get_file.assert_not_awaited()
    scoped_object_storage.get_file_size.assert_not_awaited()


@pytest.mark.parametrize("extension", ["png", "txt"])
@pytest.mark.parametrize("namespace", ["user-id", "flow-id", "source-flow"])
def test_s3_authorized_attachment_preserves_uploaded_content(scoped_object_storage, extension, namespace):
    """Keep object attachments from every trusted execution namespace."""
    with file_access_scope(("user-id", "flow-id", "source-flow")):
        content = Message(text="turn", files=[f"{namespace}/upload.{extension}"]).get_file_content_dicts()

    assert len(content) == 1
    if extension == "png":
        assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    else:
        assert "object upload canary" in content[0]["text"]
    call = scoped_object_storage.get_file.await_args
    assert call.args == (namespace, f"upload.{extension}") or call.kwargs == {
        "flow_id": namespace,
        "file_name": f"upload.{extension}",
    }


def test_s3_empty_nested_scope_fails_closed(scoped_object_storage):
    """Prevent a scopeless nested graph from inheriting an outer S3 permission."""
    with file_access_scope(("user-id",)), file_access_scope(()):
        assert Message(text="turn", files=["user-id/upload.png"]).get_file_content_dicts() == []

    scoped_object_storage.get_file.assert_not_awaited()


async def test_s3_storage_helpers_enforce_current_namespace(scoped_object_storage):
    """Apply graph namespace ownership to direct object byte reads and size probes."""
    with file_access_scope(("user-id", "flow-id")):
        with pytest.raises(StorageNamespaceError):
            await read_file_bytes("foreign-user/upload.txt")
        with pytest.raises(StorageNamespaceError):
            get_file_size("foreign-user/upload.txt")
        assert await read_file_bytes("user-id/upload.txt") == b"object upload canary user-id"
        assert get_file_size("flow-id/upload.txt") == 20
    scoped_object_storage.get_file.assert_awaited_once_with("user-id", "upload.txt")
    scoped_object_storage.get_file_size.assert_awaited_once_with("flow-id", "upload.txt")


def test_public_source_attachment_scope_remains_readable(attachment_layout):
    """Allow local attachments from a trusted public flow's source namespace."""
    source = attachment_layout.storage / "source-flow"
    source.mkdir()
    upload = source / "upload.txt"
    upload.write_text("public attachment canary")
    with file_access_scope(("user-id", "visitor-flow", "source-flow")):
        content = Message(text="turn", files=[str(upload)]).get_file_content_dicts()

    assert "public attachment canary" in content[0]["text"]


def test_empty_nested_scope_does_not_inherit_outer_access(attachment_layout):
    """Shadow outer local-file permissions while a nested graph has no trusted scopes."""
    with file_access_scope(("user-id",)), file_access_scope(()):
        assert Message(text="turn", files=[str(attachment_layout.owned)]).get_file_content_dicts() == []


@pytest.mark.parametrize("fail", [False, True])
async def test_component_execution_binds_and_restores_attachment_scope(attachment_layout, monkeypatch, fail):
    """Bind component upload permissions and restore caller scopes on success or failure."""
    from lfx.interface.initialize import loading

    vertex = SimpleNamespace(
        graph=SimpleNamespace(user_id="user-id", flow_id="flow-id", source_flow_id=None), load_from_db_fields=[]
    )
    component = SimpleNamespace(_vertex=vertex, _user_id="user-id")

    async def unchanged_params(*_args, **_kwargs):
        """Keep the test focused on execution scopes rather than parameter loading."""
        return {}

    async def convert_attachments(**_kwargs):
        """Exercise allowed and denied attachment conversion inside component execution."""
        assert Message(text="turn", files=[str(attachment_layout.foreign)]).get_file_content_dicts() == []
        content = Message(text="turn", files=[str(attachment_layout.owned)]).get_file_content_dicts()
        assert "allowed attachment canary" in content[0]["text"]
        if fail:
            msg = "component failure"
            raise RuntimeError(msg)
        return content

    monkeypatch.setattr(loading, "update_params_with_load_from_db_fields", unchanged_params)
    monkeypatch.setattr(loading, "build_component", convert_attachments)
    if fail:
        with pytest.raises(RuntimeError, match="component failure"):
            await loading.get_instance_results(component, {}, vertex)
    else:
        await loading.get_instance_results(component, {}, vertex)

    # Outside component execution there is no tenant scope, but the storage floor remains.
    content = Message(text="turn", files=[str(attachment_layout.foreign)]).get_file_content_dicts()
    assert "foreign attachment canary" in content[0]["text"]


async def test_attachment_scope_survives_sync_async_and_thread_bridges(attachment_layout):
    """Preserve attachment permissions across supported event-loop and thread bridges."""
    from lfx.utils.async_helpers import run_until_complete

    async def read_foreign_upload():
        """Attempt a foreign byte read through the synchronous event-loop bridge."""
        return await read_file_bytes(str(attachment_layout.foreign))

    with file_access_scope(("user-id", "flow-id")):
        # run_until_complete takes its thread bridge when called with an active event loop.
        with pytest.raises(LocalFileAccessError):
            run_until_complete(read_foreign_upload())
        content = await asyncio.to_thread(
            Message(text="turn", files=[str(attachment_layout.foreign)]).get_file_content_dicts
        )
        assert content == []


def test_message_flow_id_cannot_select_another_users_attachment_scope(attachment_layout):
    """Use trusted execution scopes instead of a flow ID supplied in a message payload."""
    with file_access_scope(("user-id", "flow-id")):
        message = Message(text="turn", flow_id="other-user", files=[str(attachment_layout.foreign)])
        assert message.get_file_content_dicts() == []


@pytest.mark.parametrize("target", ["outside", "reserved"])
async def test_local_storage_helpers_apply_containment_without_resolver(attachment_layout, target):
    """Apply the storage-root floor to direct local reads and size probes."""
    path = str(getattr(attachment_layout, target))
    with pytest.raises(LocalFileAccessError):
        get_file_size(path)
    with pytest.raises(LocalFileAccessError):
        await read_file_bytes(path)
    with pytest.raises(LocalFileAccessError):
        await read_file_text(path, newline="")


def test_operator_opt_out_preserves_standalone_local_attachments(attachment_layout, monkeypatch):
    """Retain unrestricted standalone reads when the operator explicitly opts out."""
    from lfx.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "restrict_local_file_access", False)
    content = Message(text="turn", files=[str(attachment_layout.outside)]).get_file_content_dicts()

    assert "outside attachment canary" in content[0]["text"]
