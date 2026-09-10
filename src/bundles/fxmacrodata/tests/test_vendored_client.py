"""Keep the bundled client reproducible and independent of an external package."""

import hashlib
import json
import re
import subprocess
import sys
from importlib.resources import files
from unittest.mock import patch

import pytest
import requests

from lfx_fxmacrodata import FXMacroDataQuery
from lfx_fxmacrodata import _public_client as public_client

CLIENT_ROOT = files(public_client)
CHECKSUMS = re.findall(r"^([a-f0-9]{64})  ([^\n]+)$", CLIENT_ROOT.joinpath("NOTICE").read_text(), re.MULTILINE)


@pytest.mark.parametrize(("expected", "filename"), CHECKSUMS, ids=[name for _, name in CHECKSUMS])
def test_public_client_matches_original_release(expected, filename):
    assert len(CHECKSUMS) == 6
    assert hashlib.sha256(CLIENT_ROOT.joinpath(filename).read_bytes()).hexdigest() == expected


def test_components_load_without_external_public_client():
    code = """
import importlib.abc
import sys

class BlockExternalClient(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'fxmacrodata_public' or fullname.startswith('fxmacrodata_public.'):
            raise ImportError('External public client must not be imported')

sys.meta_path.insert(0, BlockExternalClient())
from lfx_fxmacrodata import FXMacroDataTools
from lfx_fxmacrodata._public_client import list_operations
component = FXMacroDataTools()
component.set(api_key='', timeout=30)
assert len(component.build_tools()) == len(list_operations()) == 72
"""
    subprocess.run([sys.executable, "-I", "-c", code], check=True, capture_output=True, text=True)


def test_table_uses_bundled_http_client_and_preserves_source_links():
    payload = {"data": [{"fixture": "synthetic-vendored-transport", "value": None}]}
    response = requests.Response()
    response.status_code = 200
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(payload).encode()
    response._content_consumed = True
    component = FXMacroDataQuery()
    component.set(operation="release_calendar", arguments={"currency": "USD"}, api_key="", timeout=30)
    with patch("lfx_fxmacrodata._public_client.client.requests.Session.request", return_value=response) as request:
        frame = component.build_table()
    assert request.call_args.args[1].startswith("https://api.fxmacrodata.com/v1/")
    assert "api_key" not in request.call_args.kwargs["params"]
    assert frame.attrs["fxmacrodata_response"] == payload
    assert "fxmacrodata.com" in frame.attrs["source_url"]
    assert "utm_source=langflow" in frame.attrs["provider_url"]
