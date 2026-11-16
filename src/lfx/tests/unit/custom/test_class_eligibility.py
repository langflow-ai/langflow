"""Tests for the component class cache's best-effort mistake guard (``lfx.custom.class_eligibility``)."""

import contextlib
import json
from pathlib import Path

import pytest
from lfx.custom import class_cache, class_eligibility
from lfx.custom.eval import eval_custom_component_code

import lfx

HEADER = """
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
"""


def make_source(name: str = "CacheProbeA", body: str = "return self.text", extra: str = "") -> str:
    return (
        HEADER
        + extra
        + f"""

class {name}(Component):
    display_name = "{name}"
    inputs = [MessageTextInput(name="text", display_name="Text", value="hello")]
    outputs = [Output(name="out", display_name="Out", method="run")]

    def run(self):
        {body}
"""
    )


@pytest.fixture(autouse=True)
def _clean_cache():
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()
    yield
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()


@pytest.fixture
def cache_on(monkeypatch):
    """Enable the cache and trust every source so these tests exercise the guard alone."""
    monkeypatch.setattr(class_cache, "_read_policy", lambda: (True, 256))
    monkeypatch.setattr(class_cache, "_is_trusted_source", lambda _code: True)


def build(source: str, name: str | None = None):
    return eval_custom_component_code(source, class_name=name, reuse_class=True)


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ("SIDE = list()\n", "top_level_assignment"),
        ("print('hi')\n", "top_level_expr"),
        ("STATE = {'a': list()}\n", "top_level_assignment"),
        ("try:\n    import json\nexcept ImportError:\n    json = None\n", "top_level_try"),
        ("GLOBAL_COUNT = 0\n\ndef bump():\n    global GLOBAL_COUNT\n    GLOBAL_COUNT += 1\n", "global_or_nonlocal"),
    ],
)
@pytest.mark.usefixtures("cache_on")
def test_ineligible_sources_are_declined_but_work(extra, reason):
    source = make_source("DeclineProbe", extra=extra)
    first, second = build(source), build(source)
    assert first is not second
    assert first().run() == "hello"
    stats = class_cache.component_class_cache_stats()
    assert stats["hits"] == 0
    assert stats["decline_reasons"].get(reason, 0) >= 1


@pytest.mark.usefixtures("cache_on")
def test_decorated_component_class_declined():
    source = make_source("DecoratedProbe").replace(
        "class DecoratedProbe(Component):", "@vector_store_connection\nclass DecoratedProbe(Component):"
    )
    source = source.replace(
        "from lfx.io import",
        "from lfx.base.vectorstores.decorators import vector_store_connection\nfrom lfx.io import",
    )
    reason = class_cache._ineligible_reason(source)
    assert reason == "decorated_class"


@pytest.mark.usefixtures("cache_on")
def test_mutable_class_attribute_declined():
    shared = make_source("SharedAttrProbe").replace('display_name = "SharedAttrProbe"', "registry = make()")
    assert class_cache._ineligible_reason(shared) == "mutable_class_attribute"
    assert class_cache._ineligible_reason(make_source("OkProbe")) is None


# ---------------------------------------------------------------------------------------------
# Mistake guard. It is NOT a sandbox: the trusted-source gate is the boundary. These cases pin what the
# guard does cover. Intentionally NOT covered (acceptable because registry source is trusted): ``type(self).x = ..``
# stores, walrus/env/time/``__import__`` inside ``inputs``, aliasing (``d = cls; d.x = 1``), a rebound
# ``staticmethod`` decorator name, starred ``inputs``.
# ---------------------------------------------------------------------------------------------

_BASE = "from lfx.custom.custom_component.component import Component\nfrom lfx.io import Output, StrInput\n"
_OUT = '    outputs = [Output(name="o", display_name="o", method="run")]\n'
_LFX = (
    _BASE + "from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER\nfrom lfx.io import DropdownInput\n"
)
_RUN = "    def run(self):\n"
_VSC = "from lfx.base.vectorstores.decorators import vector_store_connection\n"


def _component(body: str, *, head: str = _LFX, cls_attrs: str = "", name: str = "R1", extra: str = "") -> str:
    return head + extra + f"class {name}(Component):\n{cls_attrs}" + _OUT + body


def _run(statements: str, **kwargs) -> str:
    return _component(_RUN + statements, **kwargs)


GUARD_CASES = {
    # name: (source, expected decline reason)
    "classmethod_counter": (
        _component(
            "    @classmethod\n    def bump(cls):\n        cls.runs += 1\n        return cls.runs\n"
            + _RUN
            + "        return self.bump()\n",
            cls_attrs="    runs = 0\n",
        ),
        "class_level_mutation",
    ),
    "classmethod_renamed_param_store": (
        _component(
            "    @classmethod\n    def bump(klass):\n        klass.runs = 1\n" + _RUN + "        return self.bump()\n"
        ),
        "class_level_mutation",
    ),
    "classmethod_param_method_mutation": (
        _component(
            "    @classmethod\n    def bump(klass):\n        klass.items.append(1)\n" + _RUN + "        return 1\n"
        ),
        "class_level_mutation",
    ),
    "classmethod_closure_mutation": (
        _component(
            "    @classmethod\n    def bump(cls):\n        def inner():\n            cls.runs = 1\n        inner()\n"
            + _RUN
            + "        return 1\n"
        ),
        "class_level_mutation",
    ),
    "component_class_name_store": (_run("        R1.runs = 1\n        return 1\n"), "class_level_mutation"),
    "component_class_inputs_append": (_run("        R1.inputs.append(1)\n        return 1\n"), "class_level_mutation"),
    "component_class_subscript_store": (_run("        R1.table['k'] = 1\n        return 1\n"), "class_level_mutation"),
    "top_level_function_attribute": (
        _run("        return helper(self._user_id)\n", extra="def helper(uid):\n    helper.last = uid\n\n"),
        "class_level_mutation",
    ),
    "nested_class_with_inputs": (
        _run("        return 1\n", cls_attrs="    class Meta:\n        inputs = []\n"),
        "class_body_classdef",
    ),
    "setattr_on_class": (_run("        setattr(self.__class__, 'x', 1)\n        return 1\n"), "setattr_on_non_self"),
    "setattr_on_non_self": (_run("        setattr(R1, 'x', 1)\n        return 1\n"), "setattr_on_non_self"),
    "dunder_dict": (_run("        return self.__dict__\n"), "dunder_access"),
    # round-2 bypass attempts
    "getattr_dunder_string": (_run("        return getattr(self, '__class__')\n"), "dunder_string"),
    "super_thisclass": (_run("        return super().__thisclass__\n"), "dunder_access"),
    "attrgetter_dunder_string": (
        _run("        return operator.attrgetter('__class__')(self)\n", extra="import operator\n\n"),
        "dunder_string",
    ),
    "builtins_setattr": (
        _run("        builtins.setattr(R1, 'x', 1)\n        return 1\n", extra="import builtins\n\n"),
        "setattr_on_non_self",
    ),
    "function_attribute_through_dunder": (
        _run("        self.run.__func__.counter = 1\n        return 1\n"),
        "dunder_access",
    ),
    "defaults_through_dunder": (
        _run("        helper.__defaults__ = (1,)\n        return 1\n", extra="def helper(x=0):\n    return x\n\n"),
        "dunder_access",
    ),
    # module-level and class-level shapes
    "global_statement": (_run("        global COUNT\n        return 1\n", extra="COUNT = 0\n\n"), "global_or_nonlocal"),
    "top_level_side_effect": (_run("        return 1\n", extra="REG = []\nREG.append(1)\n\n"), "top_level_expr"),
    "type_checking_with_non_import": (
        _run("        return 1\n", extra="TYPE_CHECKING = False\nif TYPE_CHECKING:\n    x = 1\n\n"),
        "top_level_if",
    ),
    "mutable_list_class_attr": (
        _run("        return 1\n", cls_attrs="    names = [make()]\n"),
        "mutable_class_attribute",
    ),
    "mutable_dict_class_attr": (
        _run("        return 1\n", cls_attrs="    metadata = {'k': make()}\n"),
        "mutable_class_attribute",
    ),
    "call_class_attr": (_run("        return 1\n", cls_attrs="    query = make()\n"), "mutable_class_attribute"),
    # literal containers are only reused when nothing mutates them (module level and class level)
    "module_dict_update": (
        _run("        TABLE.update(a=2)\n        return 1\n", extra="TABLE = {'a': 1}\n\n"),
        "class_level_mutation",
    ),
    "module_dict_subscript_store": (
        _run("        TABLE['a'] = 2\n        return 1\n", extra="TABLE = {'a': 1}\n\n"),
        "class_level_mutation",
    ),
    "module_dict_aug_assign": (
        _run("        TABLE['a'] += 1\n        return 1\n", extra="TABLE = {'a': 1}\n\n"),
        "class_level_mutation",
    ),
    "module_dict_nested_append": (
        _run("        TABLE['a'].append(1)\n        return 1\n", extra="TABLE = {'a': [1]}\n\n"),
        "class_level_mutation",
    ),
    "module_dict_del": (
        _run("        del TABLE['a']\n        return 1\n", extra="TABLE = {'a': 1}\n\n"),
        "class_level_mutation",
    ),
    "module_set_difference_update": (
        _run("        SEEN.difference_update({1})\n        return 1\n", extra="SEEN = {1, 2}\n\n"),
        "class_level_mutation",
    ),
    "module_set_intersection_update": (
        _run("        SEEN.intersection_update({1})\n        return 1\n", extra="SEEN = {1, 2}\n\n"),
        "class_level_mutation",
    ),
    "class_set_symmetric_difference_update": (
        _run("        self.seen.symmetric_difference_update({1})\n        return 1\n", cls_attrs="    seen = {1}\n"),
        "class_level_mutation",
    ),
    "async_classmethod_store": (
        _component(
            "    @classmethod\n    async def bump(cls):\n        cls.runs += 1\n" + _RUN + "        return 1\n",
            cls_attrs="    runs = 0\n",
        ),
        "class_level_mutation",
    ),
    "async_top_level_function_attribute": (
        _run("        return 1\n", extra="async def helper(uid):\n    helper.last = uid\n\n"),
        "class_level_mutation",
    ),
    "class_list_self_append": (
        _run("        self.names.append(1)\n        return 1\n", cls_attrs="    names = ['a']\n"),
        "class_level_mutation",
    ),
    "class_list_classname_subscript_store": (
        _run("        R1.names[0] = 'b'\n        return 1\n", cls_attrs="    names = ['a']\n"),
        "class_level_mutation",
    ),
    "class_list_nested_self_append": (
        _run("        self.names[0].append(1)\n        return 1\n", cls_attrs="    names = [['a']]\n"),
        "class_level_mutation",
    ),
    "class_dict_cls_setitem_call": (
        _component(
            "    @classmethod\n    def bump(cls):\n        cls.table.__setitem__('a', 2)\n"
            + _RUN
            + "        return 1\n",
            cls_attrs="    table = {'a': 1}\n",
        ),
        "class_level_mutation",
    ),
    "class_dict_cls_popitem": (
        _component(
            "    @classmethod\n    def bump(cls):\n        return cls.table.popitem()\n" + _RUN + "        return 1\n",
            cls_attrs="    table = {'a': 1}\n",
        ),
        "class_level_mutation",
    ),
    "super_setattr_call": (
        _run("        super().__setattr__('a', 1)\n        return 1\n"),
        "dunder_access",
    ),
    "super_init_alias_load": (
        _run("        k = super().__init__\n        return k\n"),
        "dunder_access",
    ),
    "super_class_call": (_run("        return super().__class__()\n"), "dunder_access"),
    "super_with_args_init": (_run("        super(R1, self).__init__()\n        return 1\n"), "dunder_access"),
    "decorated_component_class": (
        _run("        return 1\n", head=_LFX + _VSC).replace(
            "class R1(Component)", "@vector_store_connection\nclass R1(Component)"
        ),
        "decorated_class",
    ),
    "class_keyword": (
        _run("        return 1\n").replace("class R1(Component)", "class R1(Component, metaclass=type)"),
        "decorated_class",
    ),
}


@pytest.mark.usefixtures("cache_on")
@pytest.mark.parametrize("name", sorted(GUARD_CASES))
def test_guard_declines_with_expected_reason(name):
    source, reason = GUARD_CASES[name]
    assert class_cache._ineligible_reason(source) == reason
    try:
        first, second = build(source), build(source)
    except ValueError:
        return  # also fails on the uncached path; nothing may be cached
    assert first is not second
    assert class_cache.component_class_cache_stats()["hits"] == 0


@pytest.mark.parametrize("name", sorted(GUARD_CASES))
def test_guard_cases_are_declined_as_untrusted_too(name, monkeypatch):
    monkeypatch.setattr(class_cache, "_read_policy", lambda: (True, 256))
    monkeypatch.setattr("lfx.utils.flow_validation.get_trusted_code_for_validation", lambda _code: None)
    source, _ = GUARD_CASES[name]
    for _ in range(2):
        with contextlib.suppress(ValueError):
            build(source)
    stats = class_cache.component_class_cache_stats()
    assert stats["size"] == 0
    assert stats["hits"] == 0
    assert stats["decline_reasons"].get("untrusted_source", 0) >= 1


@pytest.mark.usefixtures("cache_on")
def test_classmethod_cross_user_leak_is_declined_and_matches_cache_off():
    source, _ = GUARD_CASES["classmethod_counter"]
    cached = [build(source)(_user_id=u).run() for u in ("A", "B")]
    plain = [eval_custom_component_code(source)(_user_id=u).run() for u in ("A", "B")]
    assert cached == plain == [1, 1]


@pytest.mark.usefixtures("cache_on")
def test_shared_set_update_is_declined_and_matches_cache_off():
    source = _run(
        "        self.seen.difference_update({self._user_id})\n        return sorted(self.seen)\n",
        cls_attrs="    seen = {'A', 'B'}\n",
    )
    assert class_cache._ineligible_reason(source) == "class_level_mutation"
    cached = [build(source)(_user_id=u).run() for u in ("A", "B")]
    plain = [eval_custom_component_code(source)(_user_id=u).run() for u in ("A", "B")]
    assert cached == plain == [["B"], ["A"]]


def test_constant_argument_inputs_on_top_level_component_are_eligible():
    assert class_cache._ineligible_reason(make_source("EligibleProbe")) is None


POSITIVE_CASES = {
    "local_and_param_stores": _run(
        "        d = {}\n        fill(d)\n        for r in [{}, {}]:\n            r['a'] = 1\n        return d\n",
        extra="def fill(target):\n    target['k'] = 1\n\n",
    ),
    "self_and_input_stores": _run(
        "        self.mine = []\n        self.mine.append(1)\n        self.inputs[0].value = 'x'\n"
        "        self.inputs.append('junk')\n        return self.mine\n",
        cls_attrs="    inputs = [StrInput(name='a', value='hello')]\n",
    ),
    "lfx_names_in_inputs_and_class_attrs": _run(
        "        return self.a\n",
        cls_attrs=(
            "    icon = MESSAGE_SENDER_AI\n"
            "    inputs = [DropdownInput(name='a', value=MESSAGE_SENDER_USER,"
            " options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER], info='who: ' + MESSAGE_SENDER_AI)]\n"
        ),
    ),
    "replacement_list": _run(
        "        return list(self.replacement)\n", cls_attrs="    replacement = ['models_and_agents.Agent']\n"
    ),
    "module_dict_constant_read_only": _run(
        "        return TABLE.get('a')\n", extra="TABLE = {'a': 1, 'b': [1, 2], 'c': MESSAGE_SENDER_AI}\n\n"
    ),
    "class_list_read_only": _run(
        "        return list(self.names) + [n for n in R1.names]\n", cls_attrs="    names = ['a', 'b']\n"
    ),
    "super_init_and_deepcopy_calls": _component(
        "    def __init__(self, **kwargs):\n        super().__init__(**kwargs)\n\n"
        "    def __deepcopy__(self, memo):\n        return super().__deepcopy__(memo)\n" + _RUN + "        return 1\n"
    ),
    "classmethod_reads_only": _component(
        "    @classmethod\n    def limit(cls):\n        return cls.LIMIT\n" + _RUN + "        return self.limit()\n",
        cls_attrs="    LIMIT = 3\n",
    ),
    "helper_class_instance": _run(
        "        h = Helper()\n        h.value = 2\n        return h.value\n", extra="class Helper:\n    pass\n\n"
    ),
    "allowed_dunders": _run("        return type(self).__name__ + str(self.__doc__)\n"),
    "type_checking_imports_and_all": _run(
        "        return 1\n",
        extra=(
            "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from lfx.schema import Data\n\n"
            "__all__ = ['R1']\n\n"
        ),
    ),
}


@pytest.mark.usefixtures("cache_on")
@pytest.mark.parametrize("name", sorted(POSITIVE_CASES))
def test_guard_positive_cases_are_reused_with_fresh_instances(name):
    source = POSITIVE_CASES[name]
    assert class_cache._ineligible_reason(source) is None
    first, second = build(source), build(source)
    assert first is second
    one, two = first(_user_id="A"), second(_user_id="B")
    assert one is not two
    assert one.inputs is not two.inputs
    stats = class_cache.component_class_cache_stats()
    assert (stats["hits"], stats["misses"]) == (1, 1)


@pytest.mark.usefixtures("cache_on")
def test_guard_positive_behaves_like_uncached():
    source = POSITIVE_CASES["self_and_input_stores"]
    cached = [build(source)(_user_id=u).run() for u in ("A", "B")]
    plain = [eval_custom_component_code(source)(_user_id=u).run() for u in ("A", "B")]
    assert cached == plain == [[1], [1]]


@pytest.mark.usefixtures("cache_on")
def test_replacement_is_not_mutated_by_framework_template_building():
    source = POSITIVE_CASES["replacement_list"]
    cls = build(source)
    before = list(cls.replacement)
    instance = cls(_user_id="A")
    instance.to_frontend_node()
    assert cls.replacement == before == ["models_and_agents.Agent"]


# Floor check instead of a full list: a guard change that silently drops coverage fails here, while
# unrelated component edits do not.
STABLE_ELIGIBLE = (
    "input_output/ChatInput",
    "input_output/ChatOutput",
    "input_output/TextInput",
    "processing/CreateList",
    "processing/DataOperations",
    "processing/ParserComponent",
)


def _shipped_eligible_components() -> list[str]:
    index_path = Path(lfx.__file__).parent / "_assets" / "component_index.json"
    if not index_path.exists():
        pytest.skip(f"component index not found at {index_path}")
    entries = json.loads(index_path.read_text())["entries"]
    return sorted(
        f"{category}/{name}"
        for category, components in entries
        for name, component in components.items()
        if isinstance((code := ((component.get("template") or {}).get("code") or {}).get("value")), str)
        and class_cache._ineligible_reason(code) is None
    )


def test_shipped_eligible_components_floor():
    eligible = _shipped_eligible_components()
    assert len(eligible) >= 90
    missing = [name for name in STABLE_ELIGIBLE if name not in eligible]
    assert not missing, f"expected eligible but declined: {missing}"


@pytest.mark.parametrize(
    ("body", "extra", "reason"),
    [
        ("return 1", "def helper(acc=[]):\n    return acc\n\n", "mutable_default_argument"),
        ("return 1", "def helper(acc={}):\n    return acc\n\n", "mutable_default_argument"),
        ("return 1", "def helper(acc=make()):\n    return acc\n\n", "mutable_default_argument"),
        ("return 1", "def helper(*, acc=[]):\n    return acc\n\n", "mutable_default_argument"),
        ("return 1", "helper = lambda acc=[]: acc\n\n", "top_level_assignment"),
        ("return list(map(lambda x, acc=[]: acc, [1]))", "", "mutable_default_argument"),
    ],
)
def test_mutable_default_arguments_are_declined(body, extra, reason):
    assert class_eligibility.ineligible_reason(make_source("DefaultProbe", body=body, extra=extra)) == reason


def test_mutable_default_argument_on_method_is_declined():
    source = make_source("MethodDefaultProbe").replace(
        "    def run(self):", "    def helper(self, acc=[]):\n        return acc\n\n    def run(self):"
    )
    assert class_eligibility.ineligible_reason(source) == "mutable_default_argument"


def test_constant_defaults_are_eligible():
    source = make_source("ConstDefaultProbe").replace(
        "    def run(self):",
        "    def helper(self, a=1, b=(1, 2), c=None, *, d='x', e=-1):\n        return a\n\n    def run(self):",
    )
    assert class_eligibility.ineligible_reason(source) is None


@pytest.mark.parametrize(
    "decorator",
    ["@lru_cache(maxsize=None)", "@functools.cache", "@cache", "@some_wrapper"],
)
def test_caching_and_unknown_method_decorators_are_declined(decorator):
    source = make_source("DecoratorProbe", extra="import functools\nfrom functools import cache, lru_cache\n").replace(
        "    def run(self):", f"    {decorator}\n    def helper(self):\n        return 1\n\n    def run(self):"
    )
    assert class_eligibility.ineligible_reason(source) == "function_decorator"


def test_allowed_decorators_stay_eligible():
    source = make_source("AllowedDecoratorProbe").replace(
        "    def run(self):",
        "    @staticmethod\n    def a():\n        return 1\n\n"
        "    @property\n    def p(self):\n        return 1\n\n"
        "    @p.setter\n    def p(self, value):\n        self._p = value\n\n"
        "    def run(self):",
    )
    assert class_eligibility.ineligible_reason(source) is None


def test_rebound_decorator_name_is_declined():
    source = make_source("RebindProbe", extra="def staticmethod(f):\n    return f\n\n").replace(
        "    def run(self):", "    @staticmethod\n    def helper():\n        return 1\n\n    def run(self):"
    )
    assert class_eligibility.ineligible_reason(source) == "rebinds_decorator_name"


def test_replacement_and_conditional_paths_are_tracked_like_other_containers():
    ok = make_source("ReplacementOk").replace("    def run(self):", "    replacement = ['a.B']\n\n    def run(self):")
    assert class_eligibility.ineligible_reason(ok) is None
    bad = make_source("ReplacementBad", body="self.replacement.append('x')\n        return 1").replace(
        "    def run(self):", "    replacement = ['a.B']\n\n    def run(self):"
    )
    assert class_eligibility.ineligible_reason(bad) == "class_level_mutation"
    bad_paths = make_source("PathsBad", body="self.conditional_paths.append('x')\n        return 1").replace(
        "    def run(self):", "    conditional_paths = ['a']\n\n    def run(self):"
    )
    assert class_eligibility.ineligible_reason(bad_paths) == "class_level_mutation"


def test_guard_internal_error_declines_with_guard_error(monkeypatch):
    def boom(*_args, **_kwargs):
        msg = "guard bug"
        raise RuntimeError(msg)

    monkeypatch.setattr(class_eligibility, "_class_reason", boom)
    assert class_eligibility.ineligible_reason(make_source("GuardErrorProbe")) == "guard_error"


@pytest.mark.usefixtures("cache_on")
def test_guard_error_does_not_break_the_build_path(monkeypatch):
    monkeypatch.setattr(class_eligibility, "_module_reason", lambda *_a, **_k: 1 / 0)
    source = make_source("GuardErrorBuildProbe")
    first, second = build(source), build(source)
    assert first is not second
    assert first().run() == "hello"
    assert class_cache.component_class_cache_stats()["decline_reasons"].get("guard_error", 0) >= 2
