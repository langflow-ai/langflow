"""Original-file uploads must enforce the executing component's storage scope."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.file_path_security import LocalFileAccessError
from lfx_amazon.components.amazon.s3_bucket_uploader import S3BucketUploaderComponent


@pytest.fixture
def upload_context(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    (storage / "owner").mkdir(parents=True)
    settings = SimpleNamespace(restrict_local_file_access=True, config_dir=str(storage), database_url="")
    monkeypatch.setattr("lfx.utils.file_path_security.get_settings_service", lambda: SimpleNamespace(settings=settings))
    component = S3BucketUploaderComponent(strategy="Store Original File", bucket_name="test-bucket", strip_path=True)
    component._user_id = "owner"
    uploads = []
    client_creations = []

    class RecordingClient:
        def upload_file(self, filename, **kwargs):
            uploads.append((filename, kwargs, Path(filename).read_bytes()))

    def client():
        client_creations.append(True)
        return RecordingClient()

    component._s3_client = client
    return component, storage, settings, uploads, client_creations


def _input(path: str, input_kind: str):
    if input_kind == "message":
        return Message(file_path=path)
    if input_kind == "table":
        return DataFrame([{"file_path": path}])
    if input_kind == "source-files":
        return Message(source_files=[{"file_path": path}])
    return Data(file_path=path)


@pytest.mark.parametrize("input_kind", ["data", "message", "table", "source-files"])
@pytest.mark.parametrize("location", ["outside", "other-user", "secret", "symlink"])
def test_original_file_blocks_out_of_scope_before_client(upload_context, tmp_path, input_kind, location):
    component, storage, _, uploads, client_creations = upload_context
    target = {
        "outside": tmp_path / "outside.txt",
        "other-user": storage / "other-user" / "file.txt",
        "secret": storage / "secret_key",
        "symlink": tmp_path / "symlink-target.txt",
    }[location]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"synthetic private content")
    if location == "symlink":
        link = storage / "owner" / "link.txt"
        link.symlink_to(target)
        target = link
    component.data_inputs = _input(str(target), input_kind)

    with pytest.raises(LocalFileAccessError):
        component.process_files()

    assert client_creations == []
    assert uploads == []


@pytest.mark.parametrize("input_kind", ["data", "message", "table", "source-files"])
def test_original_file_uploads_owned_bytes(upload_context, input_kind):
    component, storage, _, uploads, _ = upload_context
    target = storage / "owner" / "owned.txt"
    target.write_bytes(b"owned content")
    component.data_inputs = _input(str(target), input_kind)

    component.process_files()

    assert uploads == [(str(target.resolve()), {"Bucket": "test-bucket", "Key": "owned.txt"}, b"owned content")]


def test_original_file_requires_execution_scope(upload_context):
    component, storage, _, uploads, client_creations = upload_context
    component._user_id = None
    target = storage / "owner" / "file.txt"
    target.write_bytes(b"owned content without an execution scope")
    component.data_inputs = Data(file_path=str(target))

    with pytest.raises(LocalFileAccessError, match="authenticated user or flow scope"):
        component.process_files()
    assert client_creations == []
    assert uploads == []


def test_original_file_respects_operator_opt_out(upload_context, tmp_path):
    component, _, settings, uploads, _ = upload_context
    settings.restrict_local_file_access = False
    target = tmp_path / "outside.txt"
    target.write_bytes(b"operator permitted content")
    component.data_inputs = Data(file_path=str(target))

    component.process_files()

    assert uploads[0][2] == b"operator permitted content"
