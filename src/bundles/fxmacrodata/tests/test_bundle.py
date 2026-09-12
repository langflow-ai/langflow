"""Test the installed Langflow loader, components and LangChain tool runtime."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from lfx.extension.loader import load_extension, load_installed_extensions
from lfx.extension.validate import validate_extension
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from pydantic import SecretStr

from lfx_fxmacrodata import FXMacroDataQuery, FXMacroDataTools
from lfx_fxmacrodata._public_client import Result, list_operations

PAYLOAD = {"data": [{"fixture": "synthetic", "announcement_datetime": "2026-01-01T12:00:00Z", "value": None}]}


@pytest.mark.parametrize("operation", list_operations(), ids=lambda item: item.name)
def test_structuredtool_inventory_schemas_and_execution(operation):
    component = FXMacroDataTools()
    component.set(api_key="", timeout=30)
    tool = next(tool for tool in component.build_tools() if tool.name == "fxmd_" + operation.name)
    assert tool.args_schema == operation.input_schema
    # run() preserves operation parameters unchanged; HTTP/schema validation
    # is covered by the shared public client tests.
    with patch(
        "lfx_fxmacrodata.client.FXMacroDataClient.execute", return_value=Result(operation.name, PAYLOAD)
    ) as execute:
        output = tool.invoke({})
    execute.assert_called_once_with(operation.name, {})
    assert output["data"] == PAYLOAD
    assert "utm_source=langflow" in output["provider_url"]


def test_table_original_response_schema_and_provider():
    component = FXMacroDataQuery()
    component.set(
        operation="indicator_history", arguments={"currency": "USD", "indicator": "inflation"}, api_key="", timeout=30
    )
    with patch(
        "lfx_fxmacrodata.client.FXMacroDataClient.execute", return_value=Result("indicator_history", PAYLOAD)
    ) as execute:
        frame = component.build_table()
        data = component.build_response()
    assert execute.call_count == 1
    assert isinstance(frame, DataFrame)
    assert frame.attrs["fxmacrodata_response"] == PAYLOAD
    assert frame.iloc[0]["announcement_datetime"] == "2026-01-01T12:00:00Z"
    assert isinstance(data, Data) and data.data["data"] == PAYLOAD
    assert component.build_schema().data["required"] == ["currency", "indicator"]
    assert "utm_source=langflow" in component.build_provider().text


def test_actual_bundle_validation_and_installed_discovery():
    import lfx_fxmacrodata

    root = Path(lfx_fxmacrodata.__file__).parent
    report = validate_extension(root, execute_imports=True)
    assert report.ok, report
    result = load_extension(root)
    assert result.ok, result.errors
    assert {item.class_name for item in result.components} == {"FXMacroDataQuery", "FXMacroDataTools"}
    installed = load_installed_extensions()
    matching = [result for result in installed if result.extension_id == "lfx-fxmacrodata"]
    assert matching and all(result.ok for result in matching)


def test_valid_empty_table_and_sanitized_failure():
    component = FXMacroDataQuery()
    component.set(operation="release_calendar", arguments={"currency": "USD"}, api_key="", timeout=30)
    with patch("lfx_fxmacrodata.client.FXMacroDataClient.execute", return_value=Result("release_calendar", [])):
        assert component.build_table().empty
    component._pre_run_setup()
    with (
        patch(
            "lfx_fxmacrodata.client.FXMacroDataClient.execute",
            side_effect=RuntimeError("https://example.org/?api_key=DO_NOT_DISCLOSE_SENTINEL"),
        ),
        pytest.raises(ValueError) as error,
    ):
        component.build_table()
    assert "SENTINEL" not in str(error.value)


def test_operation_change_clears_old_parameters():
    component = FXMacroDataQuery()
    config = {"arguments": {"value": {"indicator": "old"}, "info": ""}}
    updated = component.update_build_config(config, "release_calendar", "operation")
    assert updated["arguments"]["value"]["currency"] == "USD"
    assert "indicator" not in updated["arguments"]["value"]


@pytest.mark.parametrize("component_type", [FXMacroDataQuery, FXMacroDataTools])
@pytest.mark.parametrize("input_path", ["constructor", "set", "set_attributes", "set_input_value", "attribute"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_literal_credentials_stay_private_during_native_export_and_execution(component_type, input_path, wrapped):
    sentinel = "FXMD_SYNTHETIC_EXPORT_SECRET"
    key = SecretStr(sentinel) if wrapped else sentinel
    component = component_type(api_key=key) if input_path == "constructor" else component_type()
    if input_path == "set":
        component.set(api_key=key)
    elif input_path == "set_attributes":
        component.set_attributes({"api_key": key})
    elif input_path == "set_input_value":
        component.set_input_value("api_key", key)
    elif input_path == "attribute":
        component.api_key = key

    assert isinstance(component.api_key, SecretStr)
    assert component.api_key.get_secret_value() == sentinel
    node = component.to_frontend_node()
    serialized = json.dumps(node, default=str)
    assert sentinel not in serialized
    field = node["data"]["node"]["template"]["api_key"]
    assert field["value"] == ""
    assert field["password"] and field["load_from_db"]
    assert field["track_in_telemetry"] is False
    assert sentinel not in repr(component)
    # Exporting a shareable node must not erase the private runtime credential.
    assert component.api_key.get_secret_value() == sentinel

    with patch("lfx_fxmacrodata.client.FXMacroDataClient") as client:
        client.return_value.__enter__.return_value.execute.return_value = Result("data_catalogue", PAYLOAD)
        if component_type is FXMacroDataTools:
            tools = component.build_tools()
            assert len(tools) == len(list_operations())
            assert all("api_key" not in tool.args_schema.get("properties", {}) for tool in tools)
            assert sentinel not in repr(tools)
            output = next(tool for tool in tools if tool.name == "fxmd_data_catalogue").invoke({"currency": "USD"})
        else:
            component.set(operation="data_catalogue", arguments={"currency": "USD"})
            output = component.build_response().data
    client.assert_called_once_with(api_key=sentinel, timeout=30)
    assert sentinel not in str(output)
    assert "fxmacrodata.com" in output["provider_url"]


@pytest.mark.parametrize("component_type", [FXMacroDataQuery, FXMacroDataTools])
def test_resolved_global_secret_and_public_access_remain_supported(component_type):
    # Langflow's global-variable service supplies a resolved SecretStr.
    component = component_type(api_key=SecretStr("FXMD_SYNTHETIC_GLOBAL_SECRET"))
    assert component.to_frontend_node()["data"]["node"]["template"]["api_key"]["value"] == ""
    component.set(api_key="")
    assert isinstance(component.api_key, SecretStr)
    assert component.api_key.get_secret_value() == ""
    component.set(api_key=None)
    assert component.api_key is None


@pytest.mark.parametrize("input_path", ["set", "set_attributes", "set_input_value", "attribute"])
def test_changing_credential_invalidates_cached_table(input_path):
    component = FXMacroDataQuery(api_key=SecretStr("FXMD_SYNTHETIC_FIRST_SECRET"))
    component.set(operation="data_catalogue", arguments={"currency": "USD"})
    with patch("lfx_fxmacrodata.client.FXMacroDataClient") as client:
        client.return_value.__enter__.return_value.execute.return_value = Result("data_catalogue", PAYLOAD)
        component.build_response()
        if input_path == "attribute":
            component.api_key = "FXMD_SYNTHETIC_SECOND_SECRET"
        elif input_path == "set_attributes":
            component.set_attributes({"api_key": "FXMD_SYNTHETIC_SECOND_SECRET"})
        elif input_path == "set_input_value":
            component.set_input_value("api_key", "FXMD_SYNTHETIC_SECOND_SECRET")
        else:
            component.set(api_key="FXMD_SYNTHETIC_SECOND_SECRET")
        component.build_response()
    assert client.call_count == 2
    assert client.call_args.kwargs["api_key"] == "FXMD_SYNTHETIC_SECOND_SECRET"
