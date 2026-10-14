"""Process and code-loading capabilities cannot pass generated-code validation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langflow.agentic.helpers.code_security import scan_code_security
from langflow.agentic.helpers.validation import validate_component_runtime

_CODE_LOADING_MODULES = (
    "runpy",
    "_posixsubprocess",
    "nt",
    "pip",
    "ensurepip",
    "venv",
    "setuptools",
    "pkg_resources",
    "build",
    "installer",
    "webbrowser",
)


@pytest.mark.parametrize("module", _CODE_LOADING_MODULES)
@pytest.mark.parametrize("statement", ["import {module}", "import {module} as loader", "from {module} import *"])
def test_rejects_process_and_code_loader_imports(module: str, statement: str) -> None:
    result = scan_code_security(statement.format(module=module))
    assert not result.is_safe
    assert any(module in violation for violation in result.violations)


@pytest.mark.parametrize(
    "code",
    [
        "import concurrent.futures as cf\ncf.ProcessPoolExecutor()",
        "from concurrent.futures import ProcessPoolExecutor as Pool\nPool()",
        "import concurrent.futures.process as p\np.ProcessPoolExecutor()",
        "import concurrent.futures as cf\npool = getattr(cf, 'ProcessPoolExecutor')\npool()",
        "import sys\nsys.setprofile(callback)",
        "from sys import settrace as trace\ntrace(callback)",
        "import sys\nprofile = getattr(sys, 'setprofile')\nprofile(callback)",
        "import site\nsite.addsitedir('/synthetic-packages')",
        "from site import addpackage as add\nadd('/synthetic-packages', 'payload.pth', set())",
        "import site\nsite.execsitecustomize()",
        "import site\nsite.execusercustomize()",
        "import signal\nsignal.raise_signal(signal.SIGTERM)",
        "from signal import raise_signal as raise_it\nraise_it(15)",
        "import torch\ntorch.load('synthetic.pt')",
        "from torch.serialization import load as load_model\nload_model('synthetic.pt')",
        "import asyncio\nloop = asyncio.get_event_loop()\nloop.subprocess_exec(protocol, 'synthetic')",
        "import asyncio\nloop = asyncio.new_event_loop()\nloop.subprocess_shell(protocol, 'synthetic')",
        "def run(loop):\n    loop.subprocess_exec(protocol, 'synthetic')",
        "def run(loop):\n    spawn = loop.subprocess_shell\n    spawn(protocol, 'synthetic')",
        "def run(loop):\n    getattr(loop, 'subprocess_exec')(protocol, 'synthetic')",
    ],
)
def test_rejects_indirect_process_and_code_loading_apis(code: str) -> None:
    assert not scan_code_security(code).is_safe


@pytest.mark.parametrize("method", ["kill", "killpg"])
@pytest.mark.parametrize(
    "code",
    [
        "import os, signal\nos.{method}(os.getpid(), signal.SIGTERM)",
        "import os as process\nprocess.{method}(123, 15)",
        "from os import {method} as send_signal\nsend_signal(123, 15)",
        "import os\nsend_signal = os.{method}\nsend_signal(123, 15)",
        "import os\ngetattr(os, '{method}')(123, 15)",
    ],
)
def test_rejects_process_signaling(method: str, code: str) -> None:
    assert not scan_code_security(code.format(method=method)).is_safe


@pytest.mark.parametrize("module", ["torch.package", "torch.package.package_importer"])
@pytest.mark.parametrize(
    "code",
    [
        "import {module}\n{module}.PackageImporter('synthetic.pt').load_pickle('model', 'data.pkl')",
        "import {module} as package\npackage.PackageImporter('synthetic.pt').import_module('model')",
        "from {module} import PackageImporter as Loader\nLoader('synthetic.pt')",
        "import {module} as package\nloader = getattr(package, 'PackageImporter')\nloader('synthetic.pt')",
        "import {module} as package\nloaders = [package.PackageImporter]\nloaders[0]('synthetic.pt')",
    ],
)
def test_rejects_pytorch_package_loading(module: str, code: str) -> None:
    assert not scan_code_security(code.format(module=module)).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "import asyncio\nasync def run():\n    await asyncio.sleep(0)",
        "from concurrent.futures import ThreadPoolExecutor\nThreadPoolExecutor(max_workers=1)",
        "import sys\nversion = sys.version_info",
        "import site\npackages = site.getsitepackages()",
        "import numpy as np\narray = np.load('array.npy', allow_pickle=False)",
        "import torch\ntensor = torch.tensor([1, 2])",
    ],
)
def test_preserves_safe_async_threads_and_tensor_operations(code: str) -> None:
    assert scan_code_security(code).is_safe


@pytest.mark.parametrize("module", ["runpy", "_posixsubprocess"])
async def test_runtime_validation_rejects_loader_before_component_construction(module: str, monkeypatch) -> None:
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
    )
    builder = MagicMock(side_effect=AssertionError("unsafe code reached component construction"))
    monkeypatch.setattr("lfx.custom.utils.build_custom_component_template", builder)

    result = await validate_component_runtime(f"import {module}", user_id="test-user")

    assert result is not None
    assert "failed security validation" in result
    builder.assert_not_called()
