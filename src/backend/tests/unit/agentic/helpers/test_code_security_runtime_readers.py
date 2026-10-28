"""Generated components cannot recover runtime objects or read source files."""

import importlib
import inspect
from pathlib import Path

import pytest
from langflow.agentic.helpers.code_security import scan_code_security


@pytest.mark.parametrize("module", ["inspect", "linecache", "fileinput"])
@pytest.mark.parametrize(
    "source",
    [
        "import {module}",
        "import {module} as helper",
        "from {module} import *",
        "from {module} import {member}",
        "from {module} import {member} as helper",
    ],
)
def test_rejects_runtime_and_file_reader_imports(module: str, source: str) -> None:
    member = {"inspect": "getmembers", "linecache": "getlines", "fileinput": "input"}[module]
    assert not scan_code_security(source.format(module=module, member=member)).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "import inspect\nfor name, value in inspect.getmembers(inspect.currentframe()):\n"
        "    if name == 'f_globals':\n        for key, module in value.items():\n"
        "            if key == 'os':\n                module.system('unused')",
        "import linecache\ncontents = linecache.getlines('/unused')",
        "import fileinput\ncontents = fileinput.input('/unused')",
        "import dataclasses\nmembers = dataclasses.inspect.getmembers(value)",
        "from dataclasses import inspect as helper\nmembers = helper.getmembers(value)",
        "import dataclasses as data\nhelper = data.inspect\nmembers = helper.getmembers(value)",
        "import dataclasses\ngetattr(dataclasses, 'inspect').getmembers(value)",
        "import dataclasses\nvars(dataclasses)['inspect'].getmembers(value)",
        "import traceback\ncontents = traceback.linecache.getlines('/unused')",
        "from traceback import linecache as helper\ncontents = helper.getlines('/unused')",
        "import traceback\ngetattr(traceback, 'linecache').getlines('/unused')",
        "import traceback\nvars(traceback)['linecache'].getlines('/unused')",
    ],
)
def test_rejects_runtime_and_file_reader_capabilities(source: str) -> None:
    assert not scan_code_security(source).is_safe


@pytest.mark.parametrize(
    "module",
    [
        "lfx.custom.custom_component.component",
        "lfx.custom.utils",
        "lfx.custom.code_parser.code_parser",
        "lfx.events.event_manager",
        "lfx.services.manager",
        "lfx.graph.utils",
        "lfx.interface.components",
        "langflow.custom.utils",
        "langflow.interface.components",
        "langflow.services.factory",
    ],
)
@pytest.mark.parametrize(
    "source",
    [
        "import {module} as c\nc.inspect.linecache.getlines('/unused')",
        "import {module}\n{module}.inspect.linecache.getlines('/unused')",
        "from {module} import inspect as reader\nreader.linecache.getlines('/unused')",
        "from {module} import *\ninspect.linecache.getlines('/unused')",
        "import {module} as c\nreader = c.inspect\nreader.getmembers(value)",
        "import {module} as c\ngetattr(c, 'inspect').getmembers(value)",
        "import {module} as c\nvars(c)['inspect'].getmembers(value)",
        "import {module} as c\ndef read(module):\n    return module.inspect.linecache.getlines('/unused')\nread(c)",
        "import {module} as c\ngetattr(c, name).getmembers(value)",
        "import {module} as c\nvars(c)[name].getmembers(value)",
        "import {module} as c\nclass Carrier:\n    reader = c",
        "import {module} as c\ndef get_reader():\n    return c",
    ],
)
def test_rejects_shipped_runtime_reader_reexports(module: str, source: str) -> None:
    assert not scan_code_security(source.format(module=module)).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "from langflow.custom.custom_component import component as c\nc.inspect.linecache.getlines('/unused')",
        "from langflow.custom import custom_component as c\nc.component.inspect.linecache.getlines('/unused')",
        "from lfx.custom import utils as c\nc.inspect.linecache.getlines('/unused')",
        "from lfx.custom.code_parser import code_parser as c\nc.inspect.linecache.getlines('/unused')",
    ],
)
def test_rejects_runtime_readers_through_package_aliases(source: str) -> None:
    assert not scan_code_security(source).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "from lfx.custom.custom_component.component import Component",
        "from langflow.custom.custom_component import component as c\nclass Example(c.Component):\n    pass",
        "import lfx.custom.custom_component.component as c\nclass Example(c.Component):\n    pass",
        "from lfx.custom.code_parser.code_parser import CodeParser\nparser = CodeParser(source)",
        "from lfx.custom.utils import get_instance_name\nname = get_instance_name(component)",
        "from langflow.custom.utils import get_instance_name\nname = get_instance_name(component)",
        "import lfx.custom.utils as c\nname = c.get_instance_name(component)",
        "class Client:\n    inspect = None\nclient = Client()\nvalue = client.inspect",
    ],
)
def test_preserves_component_classes_and_unrelated_inspect_attributes(source: str) -> None:
    assert scan_code_security(source).is_safe


@pytest.mark.parametrize("module", ["lfx.custom.utils", "lfx.custom.code_parser.code_parser", "langflow.custom.utils"])
def test_rejects_real_shipped_file_reader_reexports(module: str, tmp_path: Path) -> None:
    marker = tmp_path / "runtime-reader-marker.txt"
    marker.write_text("review-owned marker\n", encoding="utf-8")
    exported = importlib.import_module(module).inspect
    assert exported is inspect
    assert exported.linecache.getlines(str(marker)) == ["review-owned marker\n"]

    source = f"from {module} import inspect as reader\ncontents = reader.linecache.getlines({str(marker)!r})"
    assert not scan_code_security(source).is_safe
