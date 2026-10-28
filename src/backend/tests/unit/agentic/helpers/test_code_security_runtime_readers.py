"""Generated components cannot recover runtime objects or read source files."""

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
    "source",
    [
        "import lfx.custom.custom_component.component as c\nc.inspect.linecache.getlines('/unused')",
        "import lfx.custom.custom_component.component\n"
        "lfx.custom.custom_component.component.inspect.linecache.getlines('/unused')",
        "from lfx.custom.custom_component.component import inspect as reader\nreader.linecache.getlines('/unused')",
        "from lfx.custom.custom_component.component import *\ninspect.linecache.getlines('/unused')",
        "import lfx.custom.custom_component.component as c\nreader = c.inspect\nreader.getmembers(value)",
        "import lfx.custom.custom_component.component as c\ngetattr(c, 'inspect').getmembers(value)",
        "import lfx.custom.custom_component.component as c\nvars(c)['inspect'].getmembers(value)",
        "import lfx.custom.custom_component.component as c\n"
        "def read(module):\n    return module.inspect.linecache.getlines('/unused')\nread(c)",
    ],
)
def test_rejects_shipped_component_runtime_reader_reexport(source: str) -> None:
    assert not scan_code_security(source).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "from lfx.custom.custom_component.component import Component",
        "import lfx.custom.custom_component.component as c\nclass Example(c.Component):\n    pass",
        "class Client:\n    inspect = None\nclient = Client()\nvalue = client.inspect",
    ],
)
def test_preserves_component_classes_and_unrelated_inspect_attributes(source: str) -> None:
    assert scan_code_security(source).is_safe
