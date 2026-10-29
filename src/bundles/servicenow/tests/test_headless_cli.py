"""Exported flows reject unsupported headless execution before credential setup."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("injected", [False, True])
@pytest.mark.parametrize("check_variables", [False, True])
def test_cli_export_rejects_servicenow_without_preloaded_registry(tmp_path, *, injected, check_variables):
    import lfx_servicenow
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.graph import Graph
    from lfx_servicenow.components.servicenow import ServiceNowReadRecordComponent

    chat = ChatInput(_id="chat").set(input_value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    record = ServiceNowReadRecordComponent(_id="servicenow", connection="servicenow/work").set(
        record_id=chat.message_response
    )
    output = ChatOutput(_id="output").set(input_value=record.read_record)
    exported = Graph(start=chat, end=output).dump()
    for node in exported["data"]["nodes"]:
        code = node["data"]["node"]["template"]["code"]
        code["value"] = code["value"].splitlines()
    path = tmp_path / "servicenow.json"
    path.write_text(json.dumps(exported), encoding="utf-8")
    env = os.environ.copy()
    env["LANGFLOW_ALLOW_CUSTOM_COMPONENTS"] = "true"
    # Exercise discovery when the bundle is imported directly from its source tree.
    env["LANGFLOW_SEED_DIR"] = str(Path(lfx_servicenow.__file__).parent.parent)
    env["DO_NOT_TRACK"] = "1"
    env.pop("LF_CONNECTION__SERVICENOW__WORK", None)
    env.pop("LANGFLOW_SERVICENOW_ORIGIN", None)
    if injected:
        env["LF_CONNECTION__SERVICENOW__WORK"] = "synthetic-servicenow-access"
        env["LANGFLOW_SERVICENOW_ORIGIN"] = "https://acme.service-now.com"

    result = subprocess.run(  # noqa: S603 - fixed CLI arguments and a test-generated flow
        [
            sys.executable,
            "-m",
            "lfx",
            "run",
            str(path),
            "--input-value",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "--check-variables" if check_variables else "--no-check-variables",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 1
    response = json.loads(result.stdout)
    message = "ServiceNow connections are not available in headless lfx. Run this flow on a supported Langflow server."
    if check_variables:
        assert response["exception_type"] == "IntegrationContextUnsupportedError"
        assert response["exception_message"] == message
    else:
        assert message in response["exception_message"]
    assert "LF_CONNECTION" not in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
