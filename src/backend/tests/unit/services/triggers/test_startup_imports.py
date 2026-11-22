"""Trigger policy must not select standalone helpers during application bootstrap."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("entrypoint", ["langflow.main", "langflow.services.database.models.api_key.crud"])
def test_application_imports_preserve_database_helpers_and_package_children(entrypoint):
    script = """
import importlib
import sys

importlib.import_module(sys.argv[1])

import lfx.helpers
from lfx.custom.custom_component import custom_component

models = importlib.import_module("langflow.services.database.models")
api_key = importlib.import_module("langflow.services.database.models.api_key")
assert models.api_key is api_key
assert lfx.helpers.list_flows_by_flow_folder.__module__ == "langflow.helpers.flow"
assert custom_component.list_flows_by_flow_folder is lfx.helpers.list_flows_by_flow_folder
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, entrypoint], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
