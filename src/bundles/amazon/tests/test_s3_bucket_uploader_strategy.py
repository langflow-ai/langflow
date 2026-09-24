"""Regression tests for the S3 Bucket Uploader strategy dispatch."""

import pytest
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx_amazon.components.amazon.s3_bucket_uploader import S3BucketUploaderComponent


def test_default_strategy_is_selectable_and_dispatches() -> None:
    strategy_input = next(input_ for input_ in S3BucketUploaderComponent.inputs if input_.name == "strategy")
    assert strategy_input.value in strategy_input.options

    component = S3BucketUploaderComponent()
    dispatched = []
    component.process_files_by_data = lambda: dispatched.append("data")
    component.process_files_by_name = lambda: dispatched.append("name")
    component.process_files()
    assert dispatched == ["data"]


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [("Store Data", "data"), ("Store Original File", "name")],
)
def test_strategy_options_dispatch(strategy: str, expected: str) -> None:
    component = S3BucketUploaderComponent()
    component.strategy = strategy
    dispatched = []
    component.process_files_by_data = lambda: dispatched.append("data")
    component.process_files_by_name = lambda: dispatched.append("name")
    component.process_files()
    assert dispatched == [expected]


@pytest.mark.parametrize("strategy", ["By Data", ""])
def test_saved_invalid_strategy_fails_visibly(strategy: str) -> None:
    component = S3BucketUploaderComponent()
    component.strategy = strategy

    with pytest.raises(ValueError, match="Invalid S3 upload strategy"):
        component.process_files()


@pytest.mark.parametrize(
    ("strategy", "client_method", "expected_calls"),
    [
        (
            "Store Data",
            "put_object",
            [
                {"Bucket": "test-bucket", "Key": "first.txt", "Body": "first content"},
                {"Bucket": "test-bucket", "Key": "second.txt", "Body": "second content"},
            ],
        ),
        (
            "Store Original File",
            "upload_file",
            [
                ("files/first.txt", "test-bucket", "first.txt"),
                ("files/second.txt", "test-bucket", "second.txt"),
            ],
        ),
    ],
)
def test_file_message_and_directory_table_upload(
    strategy: str,
    client_method: str,
    expected_calls: list,
) -> None:
    input_ = next(input_ for input_ in S3BucketUploaderComponent.inputs if input_.name == "data_inputs")
    assert {"Message", "Table"}.issubset(input_.input_types)

    component = S3BucketUploaderComponent()
    component.strategy = strategy
    component.bucket_name = "test-bucket"
    component.strip_path = True
    component.data_inputs = [
        Message(text="first content", file_path="files/first.txt"),
        DataFrame([{"file_path": "files/second.txt", "text": "second content"}]),
    ]

    class RecordingS3Client:
        def __init__(self):
            self.calls = []

        def put_object(self, **kwargs):
            self.calls.append(("put_object", kwargs))

        def upload_file(self, path, **kwargs):
            self.calls.append(("upload_file", (path, kwargs["Bucket"], kwargs["Key"])))

    client = RecordingS3Client()
    component._s3_client = lambda: client
    component.process_files()

    assert client.calls == [(client_method, call) for call in expected_calls]


@pytest.mark.parametrize(
    ("strategy", "error"),
    [
        ("Store Data", "file_path and text"),
        ("Store Original File", "file_path"),
    ],
)
def test_file_path_message_without_file_metadata_fails(strategy: str, error: str) -> None:
    component = S3BucketUploaderComponent()
    component.strategy = strategy
    component.data_inputs = [Message(text="files/first.txt")]

    with pytest.raises(ValueError, match=error):
        component.process_files()
