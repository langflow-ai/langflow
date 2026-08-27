from __future__ import annotations

import ast
import sys
from types import ModuleType
from typing import TypeVar, get_args

import pytest
from lfx.custom.annotation_validation import (
    UnsafeReturnAnnotationError,
    is_safe_return_annotation,
    resolve_callable_return_annotation,
    resolve_type_annotation,
    validate_return_annotations,
)
from lfx.custom.code_parser.code_parser import CodeParser
from lfx.custom.eval import eval_custom_component_code
from lfx.helpers.custom import format_type
from lfx.schema import Data
from lfx.type_extraction import post_process_type


@pytest.mark.parametrize(
    "annotation",
    [
        "str",
        "list[str]",
        "Data | str",
        "typing.Sequence[Data]",
        'list["Data"]',
        '"list[Data]"',
        "tuple[str, ...]",
        'Literal["foo-bar"]',
        'Annotated[str, "ui-label"]',
    ],
)
def test_passive_return_annotations_are_accepted(annotation: str) -> None:
    node = ast.parse(f"def build() -> {annotation}:\n    pass\n").body[0]
    assert isinstance(node, ast.FunctionDef)
    assert node.returns is not None
    assert is_safe_return_annotation(node.returns)
    validate_return_annotations(ast.Module(body=[node], type_ignores=[]))


@pytest.mark.parametrize(
    "annotation",
    [
        'open("marker", "w")',
        '(open("marker", "w"), str)[1]',
        'list[open("marker", "w")]',
        "\"(open('marker', 'w'), str)[1]\"",
        "[item for item in types]",
        "lambda: str",
    ],
)
def test_active_return_annotations_are_rejected(annotation: str) -> None:
    tree = ast.parse(f"def build() -> {annotation}:\n    pass\n")
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    assert node.returns is not None
    assert not is_safe_return_annotation(node.returns)
    with pytest.raises(UnsafeReturnAnnotationError, match="active expression"):
        validate_return_annotations(tree)


@pytest.mark.parametrize(
    "annotation_template",
    [
        "(open({marker!r}, 'w'), str)[1]",
        "list[open({marker!r}, 'w')]",
        "\"(open({marker!r}, 'w'), str)[1]\"",
    ],
)
def test_code_parser_does_not_evaluate_active_annotation(tmp_path, annotation_template: str) -> None:
    marker = tmp_path / "parser-evaluated"
    annotation = annotation_template.format(marker=str(marker))
    node = ast.parse(f"def build() -> {annotation}:\n    pass\n").body[0]
    assert isinstance(node, ast.FunctionDef)

    details = CodeParser("").parse_callable_details(node)

    assert details["return_type"] is None
    assert not marker.exists()


def test_code_parser_still_resolves_supported_types() -> None:
    parser = CodeParser("")
    parser.data["imports"] = [("lfx.schema", "Data")]

    node = ast.parse("def build() -> list[Data] | str:\n    pass\n").body[0]
    assert isinstance(node, ast.FunctionDef)

    details = parser.parse_callable_details(node)
    assert details["return_type"] == list[Data] | str


def test_static_resolver_does_not_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("LE2370_ANNOTATION_VALUE", "secret")
    annotation = ast.parse('os.environ["LE2370_ANNOTATION_VALUE"]', mode="eval").body

    assert resolve_type_annotation(annotation) is None


def test_runtime_resolver_supports_imported_aliases_and_provider_types() -> None:
    class ProviderData(Data):
        pass

    globalns = {"Payload": ProviderData}

    assert resolve_type_annotation("Payload", globalns=globalns) is ProviderData
    assert resolve_type_annotation("list[Payload]", globalns=globalns) == list[ProviderData]

    trusted_alias = resolve_type_annotation("TrustedPayload | None", globalns={"TrustedPayload": Data})
    assert get_args(trusted_alias) == (Data, type(None))


def test_runtime_resolver_reads_module_dict_without_dynamic_attribute_access() -> None:
    calls: list[str] = []

    class ProviderData(Data):
        pass

    class DescriptorProbe:
        def __get__(self, _instance, _owner):
            calls.append("descriptor")
            return ProviderData

    descriptor = DescriptorProbe()
    provider_module = ModuleType("le2370_provider")
    vars(provider_module)["Payload"] = ProviderData
    vars(provider_module)["descriptor"] = descriptor

    def module_getattr(name: str):
        calls.append(name)
        return ProviderData

    provider_module.__getattr__ = module_getattr  # type: ignore[attr-defined]
    globalns = {"provider": provider_module}

    assert resolve_type_annotation("provider.Payload", globalns=globalns) is ProviderData
    assert resolve_type_annotation("provider.descriptor", globalns=globalns) is None
    assert resolve_type_annotation("provider.missing", globalns=globalns) is None
    assert calls == []


def test_runtime_resolver_rejects_non_type_bindings_without_attribute_access() -> None:
    calls: list[str] = []

    class Hostile:
        def __getattribute__(self, name: str):
            calls.append(name)
            return super().__getattribute__(name)

    hostile = Hostile()
    provider_module = ModuleType("le2370_provider")
    vars(provider_module)["Payload"] = hostile

    assert resolve_type_annotation("Payload", globalns={"Payload": hostile}) is None
    assert resolve_type_annotation("provider.Payload", globalns={"provider": provider_module}) is None
    assert calls == []


def test_runtime_resolver_bypasses_module_subclass_attribute_hooks() -> None:
    calls: list[str] = []

    class ProviderData(Data):
        pass

    class HostileModule(ModuleType):
        def __getattribute__(self, name: str):
            calls.append(name)
            return super().__getattribute__(name)

    provider_module = HostileModule("le2370_provider")
    ModuleType.__getattribute__(provider_module, "__dict__")["Payload"] = ProviderData

    assert resolve_type_annotation("provider.Payload", globalns={"provider": provider_module}) is ProviderData
    assert calls == []


def test_runtime_resolver_rejects_hostile_metaclass_without_attribute_access() -> None:
    calls: list[str] = []

    class HostileMeta(type):
        def __getattribute__(cls, name: str):
            calls.append(name)
            return super().__getattribute__(name)

    class HostilePayload(metaclass=HostileMeta):
        pass

    assert resolve_type_annotation("Payload", globalns={"Payload": HostilePayload}) is None
    assert calls == []


def test_type_processing_does_not_invoke_class_descriptors() -> None:
    calls: list[str] = []

    class DescriptorProbe:
        def __get__(self, _instance, _owner):
            calls.append("descriptor")
            return list

    class ProviderPayload:
        __origin__ = DescriptorProbe()

    assert post_process_type(ProviderPayload) == [ProviderPayload]
    assert format_type(ProviderPayload) == "ProviderPayload"
    assert calls == []


def test_format_type_preserves_trusted_typevar_name() -> None:
    ProviderType = TypeVar("ProviderType")

    assert format_type(ProviderType) == "ProviderType"


def test_format_type_preserves_generic_alias_origin_name() -> None:
    assert format_type(dict[str, str]) == "dict"


def test_runtime_resolver_does_not_invoke_user_generic_or_union_hooks() -> None:
    calls: list[str] = []

    class ProbeMeta(type(Data)):
        def __or__(cls, _other):
            calls.append("union")
            return cls

    class ProviderData(Data, metaclass=ProbeMeta):
        @classmethod
        def __class_getitem__(cls, _item):
            calls.append("generic")
            return cls

    globalns = {"ProviderData": ProviderData}

    assert resolve_type_annotation("ProviderData[str]", globalns=globalns) is None
    assert resolve_type_annotation("ProviderData | None", globalns=globalns) is None
    assert calls == []


def test_callable_resolver_uses_function_globals_without_evaluation() -> None:
    class ProviderData(Data):
        pass

    namespace = {"ProviderAlias": ProviderData}
    exec("from __future__ import annotations\ndef build() -> ProviderAlias:\n    pass\n", namespace)  # noqa: S102

    assert resolve_callable_return_annotation(namespace["build"]) is ProviderData


def test_code_parser_does_not_import_or_invoke_user_annotation_objects(monkeypatch) -> None:
    calls: list[str] = []

    class Probe:
        @classmethod
        def __class_getitem__(cls, _item):
            calls.append("called")
            return cls

    probe = ModuleType("le2370_probe")
    probe.Probe = Probe

    def module_getattr(name: str):
        calls.append(name)
        return Probe

    probe.__getattr__ = module_getattr  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, probe.__name__, probe)

    parser = CodeParser("")
    parser.data["imports"] = [(probe.__name__, "Trigger"), (probe.__name__, "Probe")]
    node = ast.parse("def build() -> Probe[str]:\n    pass\n").body[0]
    assert isinstance(node, ast.FunctionDef)

    details = parser.parse_callable_details(node)

    assert details["return_type"] is None
    assert calls == []


@pytest.mark.parametrize(
    "code",
    [
        'def build(value: (open("marker", "w"), str)[1]):\n    pass\n',
        'async def build(*, value: list[open("marker", "w")]):\n    pass\n',
        'value: (open("marker", "w"), str)[1]\n',
    ],
)
def test_active_parameter_and_variable_annotations_are_rejected(code: str) -> None:
    with pytest.raises(UnsafeReturnAnnotationError, match="active expression"):
        validate_return_annotations(ast.parse(code))


def test_custom_component_class_is_rejected_before_annotation_execution(tmp_path) -> None:
    marker = tmp_path / "class-evaluated"
    code = f"""\
from __future__ import annotations
from lfx.custom import Component
from lfx.io import Output
from lfx.schema import Data

class UnsafeAnnotationComponent(Component):
    outputs = [Output(name="result", display_name="Result", method="build")]

    def build(self) -> (open({str(marker)!r}, "w"), Data)[1]:
        return Data(data={{"ok": True}})
"""

    with pytest.raises(ValueError, match="active expression"):
        eval_custom_component_code(code)

    assert not marker.exists()


def test_custom_component_runtime_resolves_alias_module_and_provider_annotations() -> None:
    code = """\
from lfx.custom import Component
from lfx.schema import Data as Payload
import lfx.schema.data as schema_data

class ProviderPayload(Payload):
    pass

class CompatibleAnnotationComponent(Component):
    def imported_alias(self) -> Payload:
        return Payload(data={})

    def module_alias(self) -> schema_data.Data:
        return schema_data.Data(data={})

    def provider_type(self) -> ProviderPayload:
        return ProviderPayload(data={})
"""

    component = eval_custom_component_code(code)()

    assert component._get_method_return_type("imported_alias") == ["JSON"]
    assert component._get_method_return_type("module_alias") == ["JSON"]
    assert component._get_method_return_type("provider_type") == ["ProviderPayload"]
