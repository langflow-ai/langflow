"""Custom metadata compatibility retained while preserving zero/unknown counts."""

from collections import UserDict
from types import SimpleNamespace

import pytest
from lfx.schema.properties import Usage
from lfx.schema.token_usage import extract_usage_from_message


@pytest.mark.parametrize("metadata", [["unrelated"], "unrelated"])
def test_unsupported_legacy_outer_metadata_remains_unknown(metadata):
    assert extract_usage_from_message(SimpleNamespace(usage_metadata=None, response_metadata=metadata)) is None


@pytest.mark.parametrize("wrap_outer", [False, True])
def test_legacy_mapping_metadata_keeps_preexisting_counts(wrap_outer):
    metadata = {"token_usage": UserDict({"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})}
    if wrap_outer:
        metadata = UserDict(metadata)
    assert extract_usage_from_message(SimpleNamespace(usage_metadata=None, response_metadata=metadata)) == Usage(
        input_tokens=1, output_tokens=2, total_tokens=3
    )
