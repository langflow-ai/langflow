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
        "langflow.base.mcp.preset",
        "langflow.base.mcp.util",
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


@pytest.mark.parametrize("package", ["lfx.custom", "langflow.custom"])
@pytest.mark.parametrize(
    "source",
    [
        "from {package} import *\ncontents = utils.inspect.linecache.getlines('/unused')",
        "from {package} import *\ncontents = custom_component.component.inspect.linecache.getlines('/unused')",
        "import {package} as c\ndef read(module):\n"
        "    return module.utils.inspect.linecache.getlines('/unused')\ncontents = read(c)",
        "import {package} as c\ndef get_reader():\n"
        "    return c\ncontents = get_reader().utils.inspect.linecache.getlines('/unused')",
        "import {package} as c\nclass Carrier:\n"
        "    reader = c\ncontents = Carrier.reader.utils.inspect.linecache.getlines('/unused')",
        "import {package} as c\ndef read(namespace):\n"
        "    return namespace['utils'].inspect.linecache.getlines('/unused')\ncontents = read(vars(c))",
    ],
)
def test_rejects_runtime_readers_through_parent_packages(package: str, source: str) -> None:
    assert not scan_code_security(source.format(package=package)).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "from langflow.custom import *\ncontents = custom.utils.inspect.linecache.getlines('/unused')",
        "import langflow.custom as c\ncontents = c.custom.utils.inspect.linecache.getlines('/unused')",
        "import langflow.custom as c\ndef read(module):\n"
        "    return module.utils.inspect.linecache.getlines('/unused')\ncontents = read(c.custom)",
    ],
)
def test_rejects_runtime_readers_through_legacy_custom_alias(source: str) -> None:
    assert not scan_code_security(source).is_safe


@pytest.mark.parametrize("member", ["util", "preset"])
@pytest.mark.parametrize(
    "source",
    [
        "from langflow.base.mcp import {member} as c\nc.inspect.linecache.getlines('/unused')",
        "import langflow.base.mcp as c\nc.{member}.inspect.linecache.getlines('/unused')",
        "import langflow.base as c\nc.mcp.{member}.inspect.linecache.getlines('/unused')",
        "import langflow.base.mcp as c\ndef read(module):\n"
        "    return module.{member}.inspect.linecache.getlines('/unused')\nread(c)",
    ],
)
def test_rejects_legacy_runtime_readers_through_parent_packages(member: str, source: str) -> None:
    assert not scan_code_security(source.format(member=member)).is_safe


@pytest.mark.parametrize("package", ["lfx.base.mcp", "langflow.base.mcp"])
@pytest.mark.parametrize("member", ["util", "preset"])
def test_rejects_loaded_runtime_readers_through_mcp_wildcard_exports(package: str, member: str) -> None:
    source = (
        f"import {package}.{member}\nfrom {package} import *\ncontents = {member}.inspect.linecache.getlines('/unused')"
    )
    assert not scan_code_security(source).is_safe


@pytest.mark.parametrize(
    ("module", "package", "reader"),
    [
        ("lfx.custom.utils", "lfx", "custom.utils"),
        ("langflow.custom.utils", "langflow", "custom.utils"),
        ("lfx.base.mcp.util", "lfx.base", "mcp.util"),
        ("langflow.base.mcp.util", "langflow.base", "mcp.util"),
        ("lfx.events.event_manager", "lfx.events", "event_manager"),
        ("lfx.graph.vertex.base", "lfx.graph.vertex", "base"),
        ("lfx.interface.components", "lfx.interface", "components"),
        ("langflow.interface.components", "langflow.interface", "components"),
        ("langflow.services.auth.utils", "langflow.services.auth", "utils"),
        ("langflow.services.knowledge_base_storage.runtime", "langflow.services.knowledge_base_storage", "runtime"),
    ],
)
def test_rejects_loaded_runtime_readers_through_ancestor_wildcard_exports(
    module: str, package: str, reader: str
) -> None:
    source = f"import {module}\nfrom {package} import *\ncontents = {reader}.inspect.linecache.getlines('/unused')"
    assert not scan_code_security(source).is_safe


@pytest.mark.parametrize("package", ["lfx.custom", "langflow.custom"])
@pytest.mark.parametrize(
    "source",
    [
        "from {package} import *\nclass Example(Component):\n    pass",
        "from {package} import *\nname = utils.get_instance_name(component)",
        "from {package} import *\nclass Example(custom_component.component.Component):\n    pass",
        "import {package} as c\nclass Example(c.Component):\n    pass",
        "import {package} as c\nname = c.utils.get_instance_name(component)",
    ],
)
def test_preserves_safe_parent_package_exports(package: str, source: str) -> None:
    assert scan_code_security(source.format(package=package)).is_safe


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
        "from langflow.base.mcp.util import sanitize_mcp_name\nname = sanitize_mcp_name('example')",
        "from langflow.base.mcp.preset import MCPPresetComponent\nclass Example(MCPPresetComponent):\n    pass",
        "from langflow.custom import *\nclass Example(custom.Component):\n    pass",
        "import langflow.custom as c\nname = c.custom.utils.get_instance_name(component)",
        "class Client:\n    inspect = None\nclient = Client()\nvalue = client.inspect",
    ],
)
def test_preserves_component_classes_and_unrelated_inspect_attributes(source: str) -> None:
    assert scan_code_security(source).is_safe


@pytest.mark.parametrize(
    "module",
    [
        "lfx.custom.utils",
        "lfx.custom.code_parser.code_parser",
        "langflow.custom.utils",
        "langflow.base.mcp.util",
        "langflow.base.mcp.preset",
    ],
)
def test_rejects_real_shipped_file_reader_reexports(module: str, tmp_path: Path) -> None:
    marker = tmp_path / "runtime-reader-marker.txt"
    marker.write_text("review-owned marker\n", encoding="utf-8")
    exported = importlib.import_module(module).inspect
    assert exported is inspect
    assert exported.linecache.getlines(str(marker)) == ["review-owned marker\n"]

    source = f"from {module} import inspect as reader\ncontents = reader.linecache.getlines({str(marker)!r})"
    assert not scan_code_security(source).is_safe
