"""Regression tests for the S3 Bucket Uploader's strategy dispatch.

`process_files` dispatches through a dict keyed by the option labels, so the input's default
value has to be one of those labels -- otherwise a freshly added node uploads nothing.
"""

import pytest
from lfx_amazon.components.amazon.s3_bucket_uploader import S3BucketUploaderComponent

_STRATEGY_INPUT = next(input_ for input_ in S3BucketUploaderComponent.inputs if input_.name == "strategy")


def _run_with_stub(component):
    dispatched: list[str] = []
    component.process_files_by_data = lambda: dispatched.append("process_files_by_data")
    component.process_files_by_name = lambda: dispatched.append("process_files_by_name")
    logs: list[str] = []
    component.log = lambda *args, **kwargs: logs.append(str(args[0] if args else kwargs))
    component.process_files()
    return dispatched, logs


def test_default_strategy_is_one_of_the_offered_options():
    assert _STRATEGY_INPUT.value in _STRATEGY_INPUT.options


def test_default_strategy_uploads_instead_of_bailing_out():
    component = S3BucketUploaderComponent()

    dispatched, logs = _run_with_stub(component)

    assert dispatched == ["process_files_by_data"], f"{component.strategy!r} logged {logs} and uploaded nothing"


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        ("Store Data", "process_files_by_data"),
        ("Store Original File", "process_files_by_name"),
    ],
)
def test_every_option_reaches_its_handler(strategy, expected):
    component = S3BucketUploaderComponent()
    component.strategy = strategy

    dispatched, logs = _run_with_stub(component)

    assert dispatched == [expected], f"{strategy!r} logged {logs}"
