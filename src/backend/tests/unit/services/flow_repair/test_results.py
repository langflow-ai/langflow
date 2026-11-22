"""Repair outcomes expose policy diagnostics without arbitrary exception details."""

from uuid import uuid4

import pytest
from langflow.services.flow_repair.service import _failed_result
from lfx.services.model_provider_policy import ModelProviderPolicyError, ModelProviderPolicyPurpose
from lfx.utils.flow_validation import CatalogPolicyValidationError, CustomComponentValidationError


@pytest.mark.parametrize("error_type", [CustomComponentValidationError, CatalogPolicyValidationError])
def test_known_component_policy_diagnostics_are_preserved(error_type):
    message = "Flow build blocked: custom components are not allowed: Edited prompt (edited-node)"

    result = _failed_result(uuid4(), error_type(message))

    assert result.status == "manual"
    assert result.reason_codes == ["owner_policy_denied"]
    assert result.reason_detail == message


@pytest.mark.parametrize("error_type", [PermissionError, RuntimeError, ValueError])
def test_unexpected_exception_details_stay_private(error_type):
    result = _failed_result(uuid4(), error_type("private provider credential or connection details"))

    assert result.reason_detail is None
    assert "private provider" not in result.model_dump_json()


def test_provider_denial_names_the_policy_and_provider():
    result = _failed_result(uuid4(), ModelProviderPolicyError("openai", ModelProviderPolicyPurpose.USE))
    assert result.status == "manual"
    assert result.reason_codes == ["owner_policy_denied"]
    assert result.reason_detail == "The flow owner's model provider policy does not allow OpenAI."
