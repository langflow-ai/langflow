from __future__ import annotations

import ast
import importlib.util
import sys
import typing
from types import ModuleType
from typing import TypeVar, get_args

import pytest
from lfx.components.processing.output_parser import OutputParserComponent
from lfx.custom import annotation_validation
from lfx.custom.annotation_validation import (
    UnsafeReturnAnnotationError,
    is_safe_return_annotation,
    resolve_callable_return_annotation,
    resolve_compiled_method_return_annotation,
    resolve_type_annotation,
    snapshot_trusted_class_method_returns,
    validate_return_annotations,
)
from lfx.custom.code_parser.code_parser import CodeParser
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.validate import create_class
from lfx.field_typing.constants import OutputParser
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


def test_annotated_metadata_calls_are_accepted_without_execution(tmp_path) -> None:
    marker = tmp_path / "annotated-metadata-evaluated"
    tree = ast.parse(
        f'def build() -> Annotated[str, Field(description="label"), open({str(marker)!r}, "w")]:\n    pass\n'
    )
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    assert node.returns is not None

    validate_return_annotations(tree)
    resolved = resolve_type_annotation(node.returns)

    assert resolved is str
    assert not marker.exists()


def test_annotated_type_calls_remain_rejected() -> None:
    tree = ast.parse('def build() -> Annotated[open("marker", "w"), "label"]:\n    pass\n')

    with pytest.raises(UnsafeReturnAnnotationError, match="active expression"):
        validate_return_annotations(tree)


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


@pytest.mark.parametrize(
    "runtime_annotation",
    [
        typing.Sequence[int],
        typing.Iterator[str],
        typing.AsyncIterator[Data],
        typing.Iterable[float],
        typing.Mapping[str, Data],
        typing.Callable[[str, int], Data],
    ],
)
def test_runtime_resolver_supports_trusted_typing_abc_origins(runtime_annotation: object) -> None:
    assert resolve_type_annotation("Alias", globalns={"Alias": runtime_annotation}) == runtime_annotation


def test_runtime_resolver_unwraps_annotated_metadata() -> None:
    assert resolve_type_annotation(typing.Annotated[str, "label"]) is str


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


def test_callable_resolver_preserves_server_owned_output_parser_typevar() -> None:
    return_type = resolve_callable_return_annotation(OutputParserComponent.build_parser)

    assert return_type is OutputParser
    assert format_type(return_type) == "OutputParser"


def test_static_resolvers_preserve_server_owned_output_parser_typevar() -> None:
    node = ast.parse("def build() -> OutputParser:\n    pass\n").body[0]
    assert isinstance(node, ast.FunctionDef)

    assert resolve_type_annotation("OutputParser") is OutputParser
    return_type = CodeParser("").parse_callable_details(node)["return_type"]
    assert return_type is OutputParser
    assert format_type(return_type) == "OutputParser"


def test_output_parser_frontend_metadata_preserves_output_type() -> None:
    node = OutputParserComponent().to_frontend_node()["data"]["node"]
    output = next(output for output in node["outputs"] if output["name"] == "output_parser")

    assert output["types"] == ["OutputParser"]
    assert output["selected"] == "OutputParser"
    assert "OutputParser" in node["base_classes"]


def test_runtime_resolver_does_not_trust_user_output_parser_typevar() -> None:
    user_output_parser = TypeVar("OutputParser")  # noqa: PLC0132 - intentionally spoofs the trusted name

    assert resolve_type_annotation("OutputParser", globalns={"OutputParser": user_output_parser}) is None


def test_format_type_preserves_generic_alias_origin_name() -> None:
    assert format_type(dict[str, str]) == "dict"


def test_format_type_preserves_typing_generic_alias_origin_name() -> None:
    assert format_type(typing.AsyncIterator[str]) == "AsyncIterator"


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


def test_code_parser_resolves_safe_imported_aliases_without_importing() -> None:
    parser = CodeParser("")
    parser.data["imports"] = [("lfx.schema", "Data as Payload")]
    node = ast.parse("def build() -> Payload:\n    pass\n").body[0]
    assert isinstance(node, ast.FunctionDef)

    details = parser.parse_callable_details(node)

    assert details["return_type"] is Data


def test_legacy_custom_component_preserves_safe_aliased_return_type() -> None:
    from lfx.custom import CustomComponent

    code = """\
from lfx.custom import CustomComponent
from lfx.schema import Data as Payload

class AliasedAnnotationComponent(CustomComponent):
    def build(self) -> Payload:
        return Payload(data={})
"""
    component = CustomComponent(_code=code, _function_entrypoint_name="build")

    assert component._get_function_entrypoint_return_type == [Data]


def test_legacy_custom_component_skips_unresolved_return_types() -> None:
    from lfx.custom import CustomComponent

    code = """\
from lfx.custom import CustomComponent

class UnknownAnnotationComponent(CustomComponent):
    def build(self) -> MissingProviderType:
        return None
"""
    component = CustomComponent(_code=code, _function_entrypoint_name="build")

    assert component._get_function_entrypoint_return_type == []


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


def test_custom_component_uses_annotated_wrapped_type_without_executing_metadata(tmp_path) -> None:
    marker = tmp_path / "annotated-component-metadata"
    code = f"""\
from typing import Annotated
from pydantic import Field
from lfx.custom import Component

class CompatibleAnnotatedMetadataComponent(Component):
    def build(self) -> Annotated[str, Field(description="label"), open({str(marker)!r}, "w")]:
        return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert isinstance(component_class.build.__annotations__["return"], str)
    assert component_class()._get_method_return_type("build") == ["Text"]
    assert not marker.exists()


def test_custom_component_supports_abc_base_class() -> None:
    code = """\
from abc import ABC, abstractmethod
from lfx.custom import Component

class AbstractHelper(ABC):
    @abstractmethod
    def helper(self) -> str:
        raise NotImplementedError

class ABCCompatibleComponent(AbstractHelper, Component):
    def helper(self) -> str:
        return "ok"

    def build(self) -> str:
        return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == ["Text"]


def test_custom_component_preserves_unrelated_pydantic_annotated_field_metadata() -> None:
    code = """\
from typing import Annotated
from pydantic import BaseModel, Field
from lfx.custom import Component

class HelperModel(BaseModel):
    value: Annotated[int, Field(gt=0)]

HelperModelReady = HelperModel.model_rebuild(_types_namespace=globals())

class PydanticHelperAnnotationComponent(Component):
    Helper = HelperModel

    def build(self) -> str:
        return "ok"
"""

    component_class = eval_custom_component_code(code)
    metadata = component_class.Helper.model_fields["value"].metadata

    assert any(getattr(item, "gt", None) == 0 for item in metadata)
    assert component_class()._get_method_return_type("build") == ["Text"]


def test_custom_component_supports_cached_decorated_output_method() -> None:
    code = """\
from functools import lru_cache
from lfx.custom import Component

class CachedOutputComponent(Component):
    @lru_cache
    def build(self) -> str:
        return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == ["Text"]


def test_runtime_subclass_inherits_cached_decorated_sidecar_return() -> None:
    code = """\
from functools import lru_cache
from lfx.custom import Component

class CachedSidecarBaseComponent(Component):
    @lru_cache
    def build(self) -> str:
        return "ok"
"""
    base_class = eval_custom_component_code(code)

    class RuntimeSubclass(base_class):
        pass

    assert base_class()._get_method_return_type("build") == ["Text"]
    assert RuntimeSubclass()._get_method_return_type("build") == ["Text"]


def test_compiled_sidecar_is_authoritative_for_unannotated_decorated_method() -> None:
    code = """\
from lfx.custom import Component

annotation_calls = []

class PoisonAnnotations(dict):
    def get(self, key, default=None):
        annotation_calls.append(key)
        return str

def poison_annotations(function):
    function.__annotations__ = PoisonAnnotations()
    return function

class UnannotatedDecoratedComponent(Component):
    @poison_annotations
    def build(self):
        return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == []
    assert component_class.build.__globals__["annotation_calls"] == []


def test_compiled_sidecar_registry_does_not_hash_component_classes() -> None:
    code = """\
from lfx.custom import Component

hash_calls = []

class HashProbeMeta(type):
    def __hash__(cls):
        hash_calls.append("hash")
        return type.__hash__(cls)

class HashSafeComponent(Component, metaclass=HashProbeMeta):
    def build(self) -> str:
        return "ok"
"""

    component_class = eval_custom_component_code(code)
    hash_calls = component_class.build.__globals__["hash_calls"]

    assert hash_calls == []
    assert component_class()._get_method_return_type("build") == ["Text"]
    assert hash_calls == []


@pytest.mark.parametrize("return_annotation", ["SelfTypedComponent", "list[SelfTypedComponent]"])
def test_compiled_sidecar_registry_does_not_retain_self_typed_component(return_annotation: str) -> None:
    import gc
    import weakref

    code = f"""\
from lfx.custom import Component

class SelfTypedComponent(Component):
    def build(self) -> {return_annotation}:
        return self
"""

    component_class = eval_custom_component_code(code)
    class_reference = weakref.ref(component_class)

    assert component_class()._get_method_return_type("build") == []

    del component_class
    gc.collect()

    assert class_reference() is None


@pytest.mark.parametrize("return_annotation", ["LocalPayload", "list[LocalPayload]"])
def test_compiled_sidecar_registry_does_not_retain_refreshed_local_payload(return_annotation: str) -> None:
    import gc
    import weakref

    code = f"""\
import weakref
from lfx.custom import Component

payload_references = []

def make_local_payload():
    class LocalPayload:
        def marker(self):
            return "payload"

    globals()["LocalPayload"] = LocalPayload
    payload_references.append(weakref.ref(LocalPayload))
    return LocalPayload

class LocalPayloadComponent(Component):
    Payload = make_local_payload()

    def build(self) -> {return_annotation}:
        return self.Payload()
"""

    component_class = eval_custom_component_code(code)
    component_reference = weakref.ref(component_class)
    payload_reference = weakref.ref(component_class.Payload)

    assert component_class()._get_method_return_type("build") == []

    del component_class
    gc.collect()

    assert component_reference() is None
    assert payload_reference() is None


def test_compiled_sidecar_collects_control_flow_methods_without_runtime_annotation_reads() -> None:
    code = """\
from lfx.custom import Component

annotation_calls = []

class PoisonAnnotations(dict):
    def get(self, key, default=None):
        annotation_calls.append(key)
        return str

def poison_annotations(function):
    function.__annotations__ = PoisonAnnotations()
    return function

class ControlFlowMethodComponent(Component):
    if True:
        @poison_annotations
        def build(self) -> str:
            return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == []
    assert component_class.build.__globals__["annotation_calls"] == []


def test_compiled_sidecar_does_not_infer_mutually_exclusive_control_flow_return() -> None:
    code = """\
from lfx.custom import Component
from lfx.schema import Data

class ConditionalMethodComponent(Component):
    if True:
        def build(self) -> str:
            return "ok"
    else:
        def build(self) -> Data:
            return Data(data={})
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == []


def test_compiled_target_inherits_plain_same_source_base_return() -> None:
    code = """\
from lfx.custom import Component
from lfx.schema import Data

class SameSourceBase:
    def build(self) -> Data:
        return Data(data={})

class InheritedSameSourceComponent(SameSourceBase, Component):
    pass
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == ["JSON"]


def test_compiled_target_inherits_snapshotted_server_base_return() -> None:
    code = """\
from lfx.components.processing.output_parser import OutputParserComponent

class InheritedOutputParserComponent(OutputParserComponent):
    pass
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build_parser") == ["OutputParser"]
    assert component_class()._get_method_return_type("format_instructions") == ["Message"]


@pytest.mark.parametrize(
    ("import_code", "base_name"),
    [
        (
            "import lfx.components.processing.output_parser as output_parser",
            "output_parser.OutputParserComponent",
        ),
        (
            "import lfx.components.processing.output_parser",
            "lfx.components.processing.output_parser.OutputParserComponent",
        ),
    ],
)
def test_compiled_target_inherits_module_qualified_server_base_return(import_code: str, base_name: str) -> None:
    code = f"""\
{import_code}

class QualifiedInheritedComponent({base_name}):
    pass
"""

    component_class = create_class(code, "QualifiedInheritedComponent")

    assert component_class()._get_method_return_type("build_parser") == ["OutputParser"]
    assert component_class()._get_method_return_type("format_instructions") == ["Message"]


def test_same_name_rebinding_cannot_register_forged_server_sidecar() -> None:
    original_name = OutputParserComponent.__name__
    original_module = OutputParserComponent.__module__
    before = resolve_compiled_method_return_annotation(OutputParserComponent, "build_parser")
    code = """\
from lfx.components.processing.output_parser import OutputParserComponent as TrustedBase

class OutputParserComponent:
    def build_parser(self) -> str:
        return "forged"

OutputParserComponent = TrustedBase
OutputParserComponent.__name__ = "OutputParserComponent"
OutputParserComponent.__module__ = __name__

class ReboundOutputParserComponent(OutputParserComponent):
    pass
"""

    try:
        component_class = eval_custom_component_code(code)

        assert component_class()._get_method_return_type("build_parser") == []
        assert resolve_compiled_method_return_annotation(OutputParserComponent, "build_parser") == before
    finally:
        OutputParserComponent.__name__ = original_name
        OutputParserComponent.__module__ = original_module


def test_custom_metaclass_cannot_register_forged_server_sidecar() -> None:
    original_name = OutputParserComponent.__name__
    original_qualname = OutputParserComponent.__qualname__
    original_module = OutputParserComponent.__module__
    before = resolve_compiled_method_return_annotation(OutputParserComponent, "build_parser")
    code = """\
from lfx.components.processing.output_parser import OutputParserComponent as TrustedBase

def substitute_class(name, bases, namespace):
    TrustedBase.__name__ = name
    TrustedBase.__qualname__ = name
    TrustedBase.__module__ = namespace["__module__"]
    return TrustedBase

class ForgedBase(metaclass=substitute_class):
    def build_parser(self) -> str:
        return "forged"

class MetaclassTargetComponent(ForgedBase):
    pass
"""

    try:
        component_class = create_class(code, "MetaclassTargetComponent")

        assert component_class()._get_method_return_type("build_parser") == []
        assert resolve_compiled_method_return_annotation(OutputParserComponent, "build_parser") == before
    finally:
        OutputParserComponent.__name__ = original_name
        OutputParserComponent.__qualname__ = original_qualname
        OutputParserComponent.__module__ = original_module


@pytest.mark.skipif(sys.version_info < (3, 14), reason="PEP 649 deferred annotations require Python 3.14")
def test_server_snapshot_does_not_evaluate_deferred_annotations(tmp_path) -> None:
    module_path = tmp_path / "deferred_annotations.py"
    module_path.write_text(
        """\
calls = []

def side_effect():
    calls.append("evaluated")
    return str

class DeferredBase:
    def build(self) -> side_effect():
        return "value"
""",
        encoding="utf-8",
    )
    module_name = "_lfx_deferred_annotation_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        assert module.calls == []

        snapshots = snapshot_trusted_class_method_returns([module.DeferredBase])

        assert snapshots == {}
        assert module.calls == []
    finally:
        sys.modules.pop(module_name, None)


def test_server_snapshot_indexes_each_source_file_once(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "multiple_methods.py"
    module_path.write_text(
        """\
class MultipleMethodsBase:
    def build_text(self) -> str:
        return "value"

    def build_number(self) -> int:
        return 1
""",
        encoding="utf-8",
    )
    module_name = "_lfx_multiple_method_annotation_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    original_walk = ast.walk
    walk_calls = 0

    def counted_walk(node):
        nonlocal walk_calls
        walk_calls += 1
        return original_walk(node)

    try:
        spec.loader.exec_module(module)
        annotation_validation._source_function_returns.cache_clear()
        monkeypatch.setattr(annotation_validation.ast, "walk", counted_walk)

        snapshots = snapshot_trusted_class_method_returns([module.MultipleMethodsBase])

        assert (id(module.MultipleMethodsBase), "build_text") in snapshots
        assert (id(module.MultipleMethodsBase), "build_number") in snapshots
        assert walk_calls == 1
    finally:
        annotation_validation._source_function_returns.cache_clear()
        sys.modules.pop(module_name, None)


def test_compiled_target_fails_closed_for_inherited_unregistered_decorated_method() -> None:
    code = """\
from lfx.custom import Component

annotation_calls = []

class PoisonAnnotations(dict):
    def get(self, key, default=None):
        annotation_calls.append(key)
        return str

def poison_annotations(function):
    function.__annotations__ = PoisonAnnotations()
    return function

class UserBase:
    @poison_annotations
    def build(self) -> str:
        return "ok"

class InheritedUserBaseComponent(UserBase, Component):
    pass
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == []
    assert component_class.build.__globals__["annotation_calls"] == []


def test_compiled_target_fails_closed_when_snapshotted_server_annotation_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_annotations = OutputParserComponent.build_parser.__annotations__
    monkeypatch.setattr(OutputParserComponent.build_parser, "__annotations__", original_annotations)
    code = """\
from lfx.components.processing.output_parser import OutputParserComponent

annotation_calls = []

class PoisonAnnotations(dict):
    def get(self, key, default=None):
        annotation_calls.append(key)
        return str

OutputParserComponent.build_parser.__annotations__ = PoisonAnnotations()

class MutatedOutputParserComponent(OutputParserComponent):
    pass
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build_parser") == []
    annotations = OutputParserComponent.build_parser.__annotations__
    assert type(annotations).get.__globals__["annotation_calls"] == []


def test_compiled_target_fails_closed_when_snapshotted_server_method_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_method = OutputParserComponent.build_parser
    monkeypatch.setattr(OutputParserComponent, "build_parser", original_method)
    code = """\
from lfx.components.processing.output_parser import OutputParserComponent

def replacement(self) -> str:
    return "replacement"

OutputParserComponent.build_parser = replacement

class ReplacedOutputParserComponent(OutputParserComponent):
    pass
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build_parser") == []


def test_unregistered_mixin_before_trusted_base_remains_fail_closed() -> None:
    code = """\
from lfx.components.processing.output_parser import OutputParserComponent

def preserve_class(component_class):
    return component_class

@preserve_class
class UnregisteredMixin:
    @property
    def build_parser(self):
        raise AssertionError("descriptor must not execute")

class MixedOutputParserComponent(UnregisteredMixin, OutputParserComponent):
    pass
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build_parser") == []


def test_runtime_subclass_fails_closed_after_compiled_sidecar_boundary() -> None:
    code = """\
from lfx.custom import Component

annotation_calls = []

class PoisonAnnotations(dict):
    def get(self, key, default=None):
        annotation_calls.append(key)
        return str

def poison_annotations(function):
    function.__annotations__ = PoisonAnnotations()
    return function

class UserBase:
    @poison_annotations
    def build(self) -> str:
        return "ok"

class InheritedUserBaseComponent(UserBase, Component):
    pass
"""

    component_class = eval_custom_component_code(code)

    class RuntimeSubclass(component_class):
        pass

    assert RuntimeSubclass()._get_method_return_type("build") == []
    assert component_class.build.__globals__["annotation_calls"] == []


def test_custom_component_preserves_class_valued_helper_attribute() -> None:
    code = """\
from lfx.custom import Component

class Helper:
    pass

class ClassValuedHelperComponent(Component):
    HelperType = Helper

    def build(self) -> str:
        return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert component_class.HelperType.__name__ == "Helper"
    assert component_class()._get_method_return_type("build") == ["Text"]


def test_runtime_subclass_override_without_sidecar_uses_callable_resolver() -> None:
    code = """\
from lfx.custom import Component

class SidecarBaseComponent(Component):
    def build(self) -> str:
        return "ok"
"""
    base_class = eval_custom_component_code(code)

    class RuntimeSubclass(base_class):
        def build(self) -> Data:
            return Data(data={})

    assert base_class()._get_method_return_type("build") == ["Text"]
    assert RuntimeSubclass()._get_method_return_type("build") == ["JSON"]


def test_custom_component_rejects_class_decorator_substitution_without_registering_framework_class() -> None:
    from lfx.custom import Component, annotation_validation

    before = resolve_compiled_method_return_annotation(Component, "build")
    code = """\
from lfx.custom import Component

def replace_with_framework(_component_class):
    return Component

@replace_with_framework
class ReplacedComponent(Component):
    def build(self) -> str:
        return "ok"
"""

    error = None
    try:
        eval_custom_component_code(code)
    except ValueError as exc:
        error = exc
    after = resolve_compiled_method_return_annotation(Component, "build")
    if after != before:
        annotation_validation._COMPILED_CLASS_METHOD_RETURNS.pop(id(Component), None)

    assert error is not None
    assert "class" in str(error).lower()
    assert after == before


def test_custom_component_preserves_identity_returning_class_decorator() -> None:
    code = """\
from lfx.custom import Component

def preserve_identity(component_class):
    return component_class

@preserve_identity
class IdentityDecoratedComponent(Component):
    def build(self) -> str:
        return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == []


def test_custom_component_fails_closed_for_fresh_class_decorator_replacement() -> None:
    code = """\
from lfx.custom import Component
from lfx.schema import Data

def replace_with_fresh_class(_component_class):
    class ReplacementComponent(Component):
        def build(self) -> Data:
            return Data(data={})

    ReplacementComponent.__module__ = __name__
    ReplacementComponent.__name__ = "FreshReplacementComponent"
    ReplacementComponent.__qualname__ = "FreshReplacementComponent"
    return ReplacementComponent

@replace_with_fresh_class
class FreshReplacementComponent(Component):
    def build(self) -> str:
        return "target"
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == []


def test_trusted_vector_store_connection_preserves_compiled_output_types() -> None:
    code = """\
from langchain_core.vectorstores import VectorStore
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection as trusted_connection
from lfx.custom import Component

@trusted_connection
class DecoratedVectorStoreComponent(Component):
    outputs = []

    def build(self) -> str:
        return "ok"

    def build_vector_store(self) -> VectorStore:
        raise NotImplementedError
"""

    component = eval_custom_component_code(code)()

    assert component._get_method_return_type("build") == ["Text"]
    assert component._get_method_return_type("as_vector_store") == ["VectorStore"]


def test_trusted_vector_store_connection_cannot_be_replaced_and_restored_during_class_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lfx.base.vectorstores import vector_store_connection_decorator as decorator_module

    monkeypatch.setattr(
        decorator_module.vector_store_connection, "__code__", decorator_module.vector_store_connection.__code__
    )
    monkeypatch.setattr(decorator_module, "_saved_trusted_code", None, raising=False)
    monkeypatch.setattr(decorator_module, "_decorator_calls", None, raising=False)
    code = """\
import lfx.base.vectorstores.vector_store_connection_decorator as decorator_module
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection as trusted_connection
from lfx.custom import Component

def replacement(component_class):
    global _decorator_calls
    _decorator_calls += 1
    component_class.untrusted_decorator_ran = True

    def as_vector_store(self):
        return "attacker-controlled"

    component_class.as_vector_store = as_vector_store
    if _decorator_calls == 2:
        vector_store_connection.__code__ = _saved_trusted_code
    return component_class

decorator_module._saved_trusted_code = trusted_connection.__code__
decorator_module._decorator_calls = 0
trusted_connection.__code__ = replacement.__code__

@trusted_connection
class SnapshotBypassComponent(Component):
    outputs = []

    def build(self) -> str:
        return "ok"

    def build_vector_store(self):
        return "safe"
"""

    component_class = eval_custom_component_code(code)
    component = component_class()

    assert not hasattr(component_class, "untrusted_decorator_ran")
    assert component._get_method_return_type("build") == ["Text"]
    assert component._get_method_return_type("as_vector_store") == ["VectorStore"]
    assert component.as_vector_store() == "safe"


def test_trusted_vector_store_connection_ignores_current_load_helper_rebinding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    validator_module = importlib.import_module("lfx.custom.validate")
    monkeypatch.setattr(
        validator_module,
        "_apply_vector_store_connection",
        getattr(validator_module, "_apply_vector_store_connection", None),
        raising=False,
    )
    code = """\
import importlib
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection as trusted_connection
from lfx.custom import Component

def attacker_helper(component_class):
    component_class.untrusted_helper_ran = True

    def as_vector_store(self):
        return "attacker-controlled"

    component_class.as_vector_store = as_vector_store
    return component_class

validator = importlib.import_module("lfx.custom.validate")
validator._apply_vector_store_connection = attacker_helper

@trusted_connection
class HelperRebindingComponent(Component):
    outputs = []

    def build(self) -> str:
        return "ok"

    def build_vector_store(self):
        return "safe"
"""

    component_class = eval_custom_component_code(code)
    component = component_class()

    assert not hasattr(component_class, "untrusted_helper_ran")
    assert component._get_method_return_type("build") == ["Text"]
    assert component._get_method_return_type("as_vector_store") == ["VectorStore"]
    assert component.as_vector_store() == "safe"


def test_trusted_vector_store_connection_ignores_prior_validate_type_poisoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    validator_module = importlib.import_module("lfx.custom.validate")

    def poisoned_output(**_kwargs):
        return None

    monkeypatch.setattr(validator_module, "VectorStore", str, raising=False)
    monkeypatch.setattr(validator_module, "Output", poisoned_output, raising=False)
    code = """\
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection
from lfx.custom import Component

@vector_store_connection
class ValidateTypePoisoningComponent(Component):
    outputs = []

    def build(self) -> str:
        return "ok"

    def build_vector_store(self):
        return "safe"
"""

    component = eval_custom_component_code(code)()

    assert component._get_method_return_type("build") == ["Text"]
    assert component._get_method_return_type("as_vector_store") == ["VectorStore"]
    assert component.outputs[0].name == "vectorstoreconnection"
    assert component.as_vector_store() == "safe"


def test_trusted_vector_store_connection_ignores_cross_load_trust_poisoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    from lfx.base.vectorstores import vector_store_connection_decorator as decorator_module

    validator_module = importlib.import_module("lfx.custom.validate")
    for name in (
        "_TRUSTED_VECTOR_STORE_CONNECTION",
        "_TRUSTED_VECTOR_STORE_CONNECTION_CODE",
        "_TRUSTED_VECTOR_STORE_OUTPUT",
        "_TRUSTED_VECTOR_STORE_OUTPUT_FACTORY",
    ):
        monkeypatch.setattr(validator_module, name, getattr(validator_module, name, None), raising=False)
    for name in ("vector_store_connection", "VectorStore", "Output"):
        monkeypatch.setattr(decorator_module, name, getattr(decorator_module, name))

    poisoning_code = """\
import importlib
import lfx.base.vectorstores.vector_store_connection_decorator as decorator_module
from lfx.custom import Component

def arbitrary_decorator(component_class):
    component_class.untrusted_decorator_ran = True

    def as_vector_store(self):
        return "poisoned"

    component_class.as_vector_store = as_vector_store
    return component_class

def arbitrary_output(*args, **kwargs):
    return None

validator = importlib.import_module("lfx.custom.validate")
validator._TRUSTED_VECTOR_STORE_CONNECTION = arbitrary_decorator
validator._TRUSTED_VECTOR_STORE_CONNECTION_CODE = arbitrary_decorator.__code__
validator._TRUSTED_VECTOR_STORE_OUTPUT = str
validator._TRUSTED_VECTOR_STORE_OUTPUT_FACTORY = arbitrary_output
decorator_module.vector_store_connection = arbitrary_decorator
decorator_module.VectorStore = str
decorator_module.Output = arbitrary_output

class PoisoningComponent(Component):
    def build(self) -> str:
        return "poison"
"""
    victim_code = """\
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection as attacker_alias
from lfx.custom import Component

@attacker_alias
class StaleSnapshotComponent(Component):
    outputs = []

    def build(self) -> str:
        return "ok"

    def build_vector_store(self):
        return "safe"
"""

    eval_custom_component_code(poisoning_code)
    component_class = eval_custom_component_code(victim_code)
    component = component_class()

    assert not hasattr(component_class, "untrusted_decorator_ran")
    assert component._get_method_return_type("build") == ["Text"]
    assert component._get_method_return_type("as_vector_store") == ["VectorStore"]
    assert component.as_vector_store() == "safe"


def test_trusted_vector_store_connection_rejects_rebound_import_alias() -> None:
    code = """\
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection as trusted_connection
from lfx.custom import Component

def arbitrary_decorator(component_class):
    return component_class

trusted_connection = arbitrary_decorator

@trusted_connection
class ReboundTrustedDecoratorComponent(Component):
    def build(self) -> str:
        return "ok"
"""

    with pytest.raises(ValueError, match="vector-store decorator alias"):
        eval_custom_component_code(code)


def test_mutated_vector_store_decorator_module_binding_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from lfx.base.vectorstores import vector_store_connection_decorator as decorator_module

    monkeypatch.setattr(
        decorator_module,
        "vector_store_connection",
        decorator_module.vector_store_connection,
    )
    code = """\
import lfx.base.vectorstores.vector_store_connection_decorator as decorator_module
from lfx.custom import Component

def vector_store_connection(component_class):
    return component_class

decorator_module.vector_store_connection = vector_store_connection

@vector_store_connection
class MutatedDecoratorBindingComponent(Component):
    def build(self) -> str:
        return "ok"
"""

    component = eval_custom_component_code(code)()

    assert component._get_method_return_type("build") == []
    assert component._get_method_return_type("as_vector_store") == []


def test_canonical_vector_store_decorator_ignores_mutated_module_function_code(monkeypatch: pytest.MonkeyPatch) -> None:
    from lfx.base.vectorstores import vector_store_connection_decorator as decorator_module

    def replacement_decorator(component_class):
        return component_class

    monkeypatch.setattr(
        decorator_module.vector_store_connection,
        "__code__",
        replacement_decorator.__code__,
    )
    code = """\
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection
from lfx.custom import Component

@vector_store_connection
class MutatedDecoratorCodeComponent(Component):
    def build(self) -> str:
        return "ok"
"""

    component = eval_custom_component_code(code)()

    assert component._get_method_return_type("build") == ["Text"]
    assert component._get_method_return_type("as_vector_store") == ["VectorStore"]


def test_canonical_vector_store_decorator_ignores_mutated_module_output_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lfx.base.vectorstores import vector_store_connection_decorator as decorator_module

    monkeypatch.setattr(decorator_module, "VectorStore", str)
    code = """\
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection
from lfx.custom import Component

@vector_store_connection
class MutatedVectorStoreBindingComponent(Component):
    def build(self) -> str:
        return "ok"

    def build_vector_store(self):
        raise NotImplementedError
"""

    component = eval_custom_component_code(code)()

    assert component._get_method_return_type("build") == ["Text"]
    assert component._get_method_return_type("as_vector_store") == ["VectorStore"]


def test_custom_component_class_snapshot_does_not_read_instance_class_property() -> None:
    code = """\
from lfx.custom import Component

class_property_calls = []
decorator_calls = 0

class Probe:
    @property
    def __class__(self):
        class_property_calls.append("class")
        return type

def isolate_snapshot(component_class):
    global decorator_calls
    decorator_calls += 1
    if decorator_calls == 1:
        globals()["probe"] = Probe()
    else:
        globals().pop("probe", None)
    return component_class

@isolate_snapshot
class CallbackSafeComponent(Component):
    def build(self) -> str:
        return "ok"
"""

    component_class = eval_custom_component_code(code)

    assert component_class()._get_method_return_type("build") == []
    assert component_class.build.__globals__["class_property_calls"] == []


def test_custom_component_rejects_spoofed_preexisting_class_decorator_substitution() -> None:
    from lfx.custom import annotation_validation

    code = """\
from lfx.custom import Component

class ForeignMeta(type):
    pass

class ForeignComponent(metaclass=ForeignMeta):
    def build(self) -> str:
        return "foreign"

ForeignComponent.__module__ = __name__
ForeignComponent.__name__ = "SpoofedComponent"
ForeignComponent.__qualname__ = "SpoofedComponent"

def replace_with_spoofed_foreign(_component_class):
    return ForeignComponent

@replace_with_spoofed_foreign
class SpoofedComponent(Component):
    def build(self) -> str:
        return "target"
"""

    error = None
    returned_class = None
    try:
        returned_class = eval_custom_component_code(code)
    except ValueError as exc:
        error = exc
    if returned_class is not None:
        annotation_validation._COMPILED_CLASS_METHOD_RETURNS.pop(id(returned_class), None)

    assert error is not None
    assert "class" in str(error).lower()


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
