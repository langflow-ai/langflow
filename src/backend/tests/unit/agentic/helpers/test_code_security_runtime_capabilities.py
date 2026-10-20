"""Generated components cannot read server files or byte-based process secrets."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langflow.agentic.helpers.code_security import scan_code_security
from langflow.agentic.helpers.validation import validate_component_runtime
from langflow.agentic.services import user_components, user_components_overlay

_CAPABILITY_CODE = (
    "value = __loader__.get_data('/synthetic-marker')",
    "import os\nvalue = os.environb",
    "import os\nvalue = os.getenvb(b'SYNTHETIC_MARKER')",
)


@pytest.mark.parametrize(
    "code",
    [
        "value = __loader__.get_data('/synthetic-marker')",
        "loader = __loader__\nvalue = loader.get_data('/synthetic-marker')",
        "value = __spec__.loader.get_data('/synthetic-marker')",
        "spec = __spec__\nvalue = spec.loader.get_data('/synthetic-marker')",
        "value = getattr(__spec__, 'loader').get_data('/synthetic-marker')",
        "loaders = [__loader__]\nvalue = loaders[0].get_data('/synthetic-marker')",
        "def read(loader):\n    return loader.get_data('/synthetic-marker')\nvalue = read(__loader__)",
        "match __loader__:\n    case loader:\n        value = loader.get_data('/synthetic-marker')",
        "from lfx.custom.validate import __loader__ as loader\nvalue = loader.get_data('/synthetic-marker')",
        "from lfx.custom.validate import __spec__ as spec\nvalue = spec.loader.get_data('/synthetic-marker')",
    ],
)
def test_rejects_bare_runtime_loaders(code: str) -> None:
    assert not scan_code_security(code).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "import os\nvalue = os.environb",
        "import os as process\nvalue = process.environb",
        "from os import environb as environment\nvalue = environment",
        "from os import *\nvalue = environb",
        "import os\nvalue = getattr(os, 'environb')",
        "import tempfile\nvalue = tempfile._os.environb",
        "import os\nvalue = os.getenvb(b'SYNTHETIC_MARKER')",
        "import os as process\nvalue = process.getenvb(b'SYNTHETIC_MARKER')",
        "from os import getenvb as read_environment\nvalue = read_environment(b'SYNTHETIC_MARKER')",
        "from os import *\nvalue = getenvb(b'SYNTHETIC_MARKER')",
        "import os\nvalue = getattr(os, 'getenvb')(b'SYNTHETIC_MARKER')",
        "import tempfile\nvalue = tempfile._os.getenvb(b'SYNTHETIC_MARKER')",
        "import os\nread_environment = os.getenvb\nvalue = read_environment(b'SYNTHETIC_MARKER')",
        "import os\nmatch os:\n    case process:\n        value = process.environb",
        "import os\nmatch [os]:\n    case [process]:\n        value = process.getenvb(b'SYNTHETIC_MARKER')",
        "import os\nmatch {'process': os}:\n    case {'process': process}:\n        value = process.environb",
    ],
)
def test_rejects_byte_based_environment_access(code: str) -> None:
    assert not scan_code_security(code).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "import os\npaths = os.get_exec_path()",
        "import os as process\npaths = process.get_exec_path()",
        "from os import get_exec_path as read_paths\npaths = read_paths()",
        "from os import *\npaths = get_exec_path()",
        "import os\npaths = getattr(os, 'get_exec_path')()",
        "import os\nread_paths = os.get_exec_path\npaths = read_paths()",
        "import tempfile\npaths = tempfile._os.get_exec_path()",
        "import os\nreaders = [os.get_exec_path]\npaths = readers[0]()",
    ],
)
def test_rejects_process_path_environment_access(code: str) -> None:
    assert not scan_code_security(code).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "import tempfile\nwith tempfile.NamedTemporaryFile() as stream:\n    stream.write(b'data')",
        "import os\nvalue = os.path.join('a', 'b')",
        "module_name = __name__\ndescription = __doc__",
        "class Config:\n    environb = {}\nvalue = Config().environb",
        "class Config:\n    def get_exec_path(self):\n        return []\npaths = Config().get_exec_path()",
        "match [1, 2]:\n    case [first, second]:\n        value = first + second",
    ],
)
def test_preserves_safe_temporary_files_metadata_and_values(code: str) -> None:
    assert scan_code_security(code).is_safe


def test_rejects_source_runner_even_when_source_is_stored_in_a_temporary_file() -> None:
    code = (
        "import tempfile, runpy\n"
        "with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as stream:\n"
        "    stream.write('marker = True')\n"
        "    stream.flush()\n"
        "    runpy.run_path(stream.name)\n"
    )
    assert not scan_code_security(code).is_safe


@pytest.mark.parametrize("code", _CAPABILITY_CODE)
async def test_runtime_validation_rejects_capability_before_component_construction(code: str, monkeypatch) -> None:
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
    )
    builder = MagicMock(side_effect=AssertionError("unsafe code reached component construction"))
    monkeypatch.setattr("lfx.custom.utils.build_custom_component_template", builder)

    result = await validate_component_runtime(code, user_id="test-user")

    assert result is not None
    assert "failed security validation" in result
    builder.assert_not_called()


@pytest.mark.parametrize("code", _CAPABILITY_CODE)
def test_registration_rejects_capability_before_resolving_component_directory(code: str, monkeypatch) -> None:
    resolve_directory = MagicMock(side_effect=AssertionError("unsafe code reached component persistence"))
    monkeypatch.setattr(user_components, "_resolve_components_dir", resolve_directory)

    with pytest.raises(user_components.UserComponentError, match="security validation"):
        user_components.register_user_component(user_id="test-user", class_name="CapabilityComponent", code=code)

    resolve_directory.assert_not_called()


@pytest.mark.parametrize("code", _CAPABILITY_CODE)
def test_overlay_rejects_persisted_capability_before_component_construction(code: str, tmp_path, monkeypatch) -> None:
    source = tmp_path / "CapabilityComponent.py"
    source.write_text(code, encoding="utf-8")
    builder = MagicMock(side_effect=AssertionError("unsafe code reached component construction"))
    monkeypatch.setattr("lfx.custom.utils.build_custom_component_template", builder)

    entry = user_components_overlay._build_overlay_entry(source, {})

    assert entry is None
    builder.assert_not_called()
