"""Generated components cannot recover objects from the server process."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langflow.agentic.helpers.code_security import scan_code_security
from langflow.agentic.helpers.validation import validate_component_runtime
from langflow.agentic.services import user_components, user_components_overlay

_RECOVERY_METHODS = ("get_objects", "get_referrers", "get_referents")
_RECOVERY_CODE = """\
import gc
from lfx.custom import Component
from lfx.io import Output
from lfx.schema import Data

class RecoveryComponent(Component):
    outputs = [Output(name="result", method="build_output")]

    def build_output(self) -> Data:
        for candidate in gc.get_objects():
            if callable(candidate) and getattr(candidate, "__name__", "") == "exec":
                candidate("marker = True")
        return Data(data={"done": True})
"""


@pytest.mark.parametrize("method", _RECOVERY_METHODS)
@pytest.mark.parametrize(
    "code",
    [
        "import gc\ngc.{method}()",
        "import gc as collector\ncollector.{method}()",
        "from gc import {method} as recover\nrecover()",
        "from gc import *\n{method}()",
        "import gc\nrecover = gc.{method}\nrecover()",
        "import gc\ngetattr(gc, '{method}')()",
        "import gc\nrecoverers = [gc.{method}]\nrecoverers[0]()",
    ],
)
def test_rejects_gc_object_recovery(method: str, code: str) -> None:
    assert not scan_code_security(code.format(method=method)).is_safe


@pytest.mark.parametrize("method", _RECOVERY_METHODS)
@pytest.mark.parametrize(
    "code",
    [
        "import gc\nmatch gc:\n    case collector:\n        collector.{method}()",
        "import gc\nmatch [gc]:\n    case [collector]:\n        collector.{method}()",
        "import gc\nmatch {{'gc': gc}}:\n    case {{'gc': collector}}:\n        collector.{method}()",
        "import gc\nmatch gc:\n    case collector if collector.{method}():\n        pass",
        "import gc\nmatch gc.{method}:\n    case recover:\n        recover()",
    ],
)
def test_rejects_gc_recovery_through_match_capture(method: str, code: str) -> None:
    assert not scan_code_security(code.format(method=method)).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "match [1, 2]:\n    case [first, second]:\n        value = first + second",
        "import gc\nmatch gc.get_count():\n    case counts:\n        total = sum(counts)",
        "class Collector:\n    def get_objects(self):\n        return []\n"
        "match Collector():\n    case collector:\n        collector.get_objects()",
    ],
)
def test_preserves_matches_of_ordinary_values(code: str) -> None:
    assert scan_code_security(code).is_safe


@pytest.mark.parametrize("method", _RECOVERY_METHODS)
@pytest.mark.parametrize(
    "body",
    [
        "    collector = None\n    del collector\n    values = collector.{method}()",
        "    collector = None\n    del collector\n    recover = collector.{method}",
        "    collector = None\n    def read(self):\n        return collector.{method}()",
        "    collector = None\n    read = lambda self: collector.{method}()",
        "    collector = None\n    values = [collector.{method}() for _ in [1]]",
        "    collector = None\n    class Inner:\n        values = collector.{method}()",
        "    def collector(self):\n        return collector.{method}()",
    ],
)
def test_rejects_gc_recovery_after_class_scope_shadowing(method: str, body: str) -> None:
    code = "import gc as collector\nclass Carrier:\n" + body.format(method=method)
    assert not scan_code_security(code).is_safe


@pytest.mark.parametrize("method", [*_RECOVERY_METHODS, "garbage"])
@pytest.mark.parametrize(
    "wrapper",
    [
        # After ``del`` in a class body, reads resolve to module globals,
        # never the enclosing function's shadow.
        "import gc as collector\ndef build():\n    collector = None\n    class Carrier:\n"
        "        collector = None\n        del collector\n        values = collector.{access}\n    return Carrier",
        "import gc as collector\ndef build(collector):\n    class Carrier:\n"
        "        collector = None\n        del collector\n        values = collector.{access}\n    return Carrier",
        "import gc as collector\ndef build():\n    collector = None\n    class Carrier:\n"
        "        class Inner:\n            collector = None\n            del collector\n"
        "            values = collector.{access}\n    return Carrier",
    ],
)
def test_rejects_gc_recovery_after_delete_in_function_nested_class(method: str, wrapper: str) -> None:
    access = method if method == "garbage" else f"{method}()"
    assert not scan_code_security(wrapper.format(access=access)).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "import gc as collector\nclass Carrier:\n    collector = None\n"
        "    def read(self):\n        return collector.collect()",
        "import gc as collector\nclass Carrier:\n    collector = None\n"
        "    def read(self, collector):\n        return collector.get_objects()",
        "import gc as collector\nclass Carrier:\n    values = [collector.get_objects() for collector in []]",
        "def build(collector):\n    class Carrier:\n        collector = None\n"
        "        del collector\n        values = collector.get_objects()\n    return Carrier",
        # Methods close over the enclosing function local, unlike direct
        # class-body reads after ``del``.
        "import gc as collector\ndef build():\n    collector = None\n    class Carrier:\n"
        "        collector = None\n        def read(self):\n"
        "            return collector.get_objects()\n    return Carrier",
        "class Local:\n    def get_objects(self):\n        return []\n"
        "class Carrier:\n    collector = Local()\n    values = collector.get_objects()",
    ],
)
def test_preserves_safe_class_scope_lookups(code: str) -> None:
    assert scan_code_security(code).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "import gc\nobjects = gc.garbage",
        "from gc import garbage as objects",
        "from gc import *\nobjects = garbage",
        "import gc\nobjects = getattr(gc, 'garbage')",
    ],
)
def test_rejects_gc_garbage_object_pool(code: str) -> None:
    assert not scan_code_security(code).is_safe


def test_rejects_gc_callable_recovery_inside_component_output() -> None:
    assert not scan_code_security(_RECOVERY_CODE).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "import gc\ngc.collect()",
        "from gc import collect as collect_now\ncollect_now()",
        "from gc import *\ncollect()",
        "import gc\ncounts = gc.get_count()\nstats = gc.get_stats()",
        "import gc\ntracked = gc.is_tracked([])\nenabled = gc.isenabled()",
    ],
)
def test_preserves_gc_collection_and_statistics(code: str) -> None:
    assert scan_code_security(code).is_safe


async def test_runtime_validation_rejects_recovery_before_component_construction(monkeypatch) -> None:
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
    )
    builder = MagicMock(side_effect=AssertionError("unsafe code reached component construction"))
    monkeypatch.setattr("lfx.custom.utils.build_custom_component_template", builder)

    result = await validate_component_runtime(_RECOVERY_CODE, user_id="test-user")

    assert result is not None
    assert "failed security validation" in result
    builder.assert_not_called()


def test_registration_rejects_recovery_before_resolving_component_directory(monkeypatch) -> None:
    resolve_directory = MagicMock(side_effect=AssertionError("unsafe code reached component persistence"))
    monkeypatch.setattr(user_components, "_resolve_components_dir", resolve_directory)

    with pytest.raises(user_components.UserComponentError, match="security validation"):
        user_components.register_user_component(
            user_id="test-user", class_name="RecoveryComponent", code=_RECOVERY_CODE
        )

    resolve_directory.assert_not_called()


def test_overlay_rejects_persisted_recovery_before_component_construction(tmp_path, monkeypatch) -> None:
    source = tmp_path / "RecoveryComponent.py"
    source.write_text(_RECOVERY_CODE, encoding="utf-8")
    builder = MagicMock(side_effect=AssertionError("unsafe code reached component construction"))
    monkeypatch.setattr("lfx.custom.utils.build_custom_component_template", builder)

    entry = user_components_overlay._build_overlay_entry(source, {})

    assert entry is None
    builder.assert_not_called()
