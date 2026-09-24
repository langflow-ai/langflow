"""Regression tests for the S3 Bucket Uploader strategy dispatch."""

import pytest
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
