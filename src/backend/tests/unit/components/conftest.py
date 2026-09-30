import importlib.util
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_googleapiclient(monkeypatch):
    if importlib.util.find_spec("googleapiclient") is not None:
        return

    googleapiclient = ModuleType("googleapiclient")
    googleapiclient.__path__ = []

    discovery = ModuleType("googleapiclient.discovery")
    discovery.build = MagicMock(name="build")

    http = ModuleType("googleapiclient.http")
    http.MediaFileUpload = MagicMock(name="MediaFileUpload")
    http.MediaIoBaseDownload = MagicMock(name="MediaIoBaseDownload")

    googleapiclient.discovery = discovery
    googleapiclient.http = http

    monkeypatch.setitem(sys.modules, "googleapiclient", googleapiclient)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", http)
