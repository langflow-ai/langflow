"""Isolation guarantees the compile cache must never trade away.

``test_component_class_isolation.py`` pins the core rule: every call to
``eval_custom_component_code`` gets its own class object. These tests cover the
axes that rule can still be broken on, each of which a caching attempt has
already reached for at least once:

* **Module namespace.** ``prepare_global_scope`` execs module-level
  ``Assign``/``FunctionDef``/``ClassDef`` into ``exec_globals``, and a built class
  carries that dict as its ``__globals__``. Caching a class therefore shares the
  component's whole module namespace, not just the class -- so a component
  keeping state in a module-level list leaks it exactly like a class attribute
  does. Caching the compiled artefacts and exec'ing fresh avoids this; these
  tests are what say so out loud.
* **Concurrency.** Sibling vertices in one graph layer build concurrently via
  ``asyncio.gather``, and FastAPI runs sync endpoints in an anyio worker
  threadpool. Isolation verified only by repetition cannot see a race.
* **The shipped components themselves.** A guarantee about the mechanism is
  worth little if a component ships state that the mechanism has to protect.

Every assertion here is written to fail if the isolation guarantee regresses,
not merely to pass today.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import importlib
import inspect
import json
import pkgutil
import textwrap
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from lfx.custom.custom_component.component import Component
from lfx.custom.eval import eval_custom_component_code

# Keeps state in the MODULE namespace rather than on the class -- the second way
# to leak, and the one a class-only isolation test cannot see.
MODULE_STATE_SOURCE = """
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

_SEEN = []


class ModuleStateComponent(Component):
    display_name = "Module State"
    inputs = [MessageTextInput(name="input_value", display_name="In")]
    outputs = [Output(display_name="Out", name="out", method="process")]

    def process(self) -> Message:
        _SEEN.append(self.input_value)
        return Message(text=f"seen={_SEEN}")
"""


def _module_globals_of(cls: type) -> dict:
    """The namespace the built class actually closes over."""
    return cls.process.__globals__


# ---------------------------------------------------------------------------
# module namespace
# ---------------------------------------------------------------------------


def test_two_builds_do_not_share_a_module_namespace():
    first = eval_custom_component_code(MODULE_STATE_SOURCE)
    second = eval_custom_component_code(MODULE_STATE_SOURCE)

    assert _module_globals_of(first) is not _module_globals_of(second)
    assert _module_globals_of(first)["_SEEN"] is not _module_globals_of(second)["_SEEN"]


def test_module_level_state_does_not_carry_between_builds():
    """The leak in its user-visible form: request 2 reading request 1's input."""
    seen = []
    for token in ("user-A-secret", "user-B-secret"):
        instance = eval_custom_component_code(MODULE_STATE_SOURCE)(_code=MODULE_STATE_SOURCE)
        instance.set(input_value=token)
        instance.process()
        seen.append(list(_module_globals_of(type(instance))["_SEEN"]))

    assert seen[0] == ["user-A-secret"]
    assert seen[1] == ["user-B-secret"], f"build 2 saw build 1's data: {seen[1]}"


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------


def _build_on_threads(source: str, count: int) -> list[type]:
    """Build ``count`` classes from one source on threads released together."""
    barrier = threading.Barrier(count)

    def build(_):
        barrier.wait()  # maximise overlap rather than trickling through
        return eval_custom_component_code(source)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(build, range(count)))


def test_concurrent_builds_of_one_source_are_mutually_isolated():
    classes = _build_on_threads(MODULE_STATE_SOURCE, 32)

    assert len({id(cls) for cls in classes}) == 32, "a class object was shared between threads"
    assert len({id(_module_globals_of(cls)) for cls in classes}) == 32, "a module namespace was shared"


def test_concurrent_builds_do_not_cross_contaminate_state():
    classes = _build_on_threads(MODULE_STATE_SOURCE, 24)
    results: dict[int, list[str]] = {}
    barrier = threading.Barrier(len(classes))

    def run(index):
        instance = classes[index](_code=MODULE_STATE_SOURCE)
        instance.set(input_value=f"thread-{index}")
        barrier.wait()
        instance.process()
        results[index] = list(_module_globals_of(classes[index])["_SEEN"])

    with ThreadPoolExecutor(max_workers=len(classes)) as pool:
        list(pool.map(run, range(len(classes))))

    for index, seen in results.items():
        assert seen == [f"thread-{index}"], f"thread {index} saw {seen}"


@pytest.mark.asyncio
async def test_builds_are_isolated_across_anyio_worker_threads():
    """The real dispatch mechanism: FastAPI runs sync endpoint work via anyio."""

    def build_and_run(index):
        instance = eval_custom_component_code(MODULE_STATE_SOURCE)(_code=MODULE_STATE_SOURCE)
        instance.set(input_value=f"anyio-{index}")
        instance.process()
        return list(_module_globals_of(type(instance))["_SEEN"])

    results = await asyncio.gather(*(asyncio.to_thread(build_and_run, i) for i in range(32)))

    assert results == [[f"anyio-{index}"] for index in range(32)]


# ---------------------------------------------------------------------------
# the shipped components
# ---------------------------------------------------------------------------


def _bundled_component_classes() -> dict[str, type]:
    import lfx.components as components_pkg

    found: dict[str, type] = {}
    for module_info in pkgutil.walk_packages(components_pkg.__path__, components_pkg.__name__ + "."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception:  # noqa: S112 - optional bundles may not be installed
            continue
        for obj in vars(module).values():
            if inspect.isclass(obj) and issubclass(obj, Component) and obj is not Component:
                found[f"{obj.__module__}.{obj.__name__}"] = obj
    return found


def _class_state(cls: type) -> dict:
    """Deep snapshot of every mutable attribute reachable on ``cls``."""
    import copy

    snapshot: dict = {}
    for key in dir(cls):
        if key.startswith("__"):
            continue
        try:
            value = inspect.getattr_static(cls, key)
        except Exception:  # noqa: S112 - unreadable attrs cannot leak
            continue
        if isinstance(value, (list, dict, set)):
            try:
                snapshot[key] = copy.deepcopy(value)
            except Exception:
                snapshot[key] = repr(value)
    return snapshot


def test_no_bundled_component_mutates_its_class_on_instantiation():
    classes = _bundled_component_classes()
    assert len(classes) > 50, f"expected a substantial component library, found {len(classes)}"

    offenders, checked = [], 0
    for name, cls in classes.items():
        before = _class_state(cls)
        try:
            instance = cls()
        except Exception:  # noqa: S112 - components needing config are out of scope
            continue
        checked += 1
        with contextlib.suppress(Exception):  # build errors are not our concern, mutation is
            instance.to_frontend_node()
        if _class_state(cls) != before:
            offenders.append(name)

    assert checked > 50, f"only {checked} components were instantiable; the sweep proves little"
    assert offenders == [], f"components mutated their own class state: {offenders}"


_MUTATING_METHODS = frozenset(
    {"append", "extend", "insert", "update", "setdefault", "pop", "clear", "add", "remove", "sort", "popitem"}
)


def _module_state_writes(source: str, label: str) -> list[str]:
    """In-place writes to module-level mutable state in ``source``."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return []

    tracked: set[str] = set()
    for node in tree.body:  # module scope only, not nested
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if node.value is not None and isinstance(node.value, (ast.List, ast.Dict, ast.Set)):
                tracked |= {t.id for t in targets if isinstance(t, ast.Name)}
    if not tracked:
        return []

    found: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _MUTATING_METHODS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in tracked
        ):
            found.append(f"{label}: {node.func.value.id}.{node.func.attr}()")
        if isinstance(node, ast.Assign):
            found.extend(
                f"{label}: {target.value.id}[...] = ..."
                for target in node.targets
                if isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id in tracked
            )
    return found


def test_module_state_detector_catches_a_deliberate_writer():
    """Teeth check: the sweep below is worthless if this cannot fire."""
    assert _module_state_writes(MODULE_STATE_SOURCE, "probe") == ["probe: _SEEN.append()"]
    assert _module_state_writes("_T = {}\nx = _T['k']\n", "probe") == []


def test_no_shipped_component_writes_to_module_level_state():
    """Component source is exec'd from the index, so that is the corpus that matters.

    A component writing request data into module-level state is safe only while
    every build gets a fresh namespace. It is one caching change away from being
    a cross-request leak, and it already was one: ``GuardrailsComponent`` stored
    the user's ``custom_guardrail_explanation`` in a module-level dict and read
    it back nine lines later.
    """
    import lfx

    index_path = Path(lfx.__file__).resolve().parent / "_assets" / "component_index.json"
    assert index_path.exists(), f"component index not found at {index_path}"

    sources: list[str] = []

    def collect(node):
        if isinstance(node, dict):
            template = node.get("template")
            if isinstance(template, dict):
                code = template.get("code")
                if isinstance(code, dict) and isinstance(code.get("value"), str):
                    sources.append(code["value"])
            for child in node.values():
                collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)

    collect(json.loads(index_path.read_text()))
    assert len(sources) > 50, f"only {len(sources)} component sources found; the sweep proves little"

    offenders: list[str] = []
    for source in sources:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        label = next((n.name for n in tree.body if isinstance(n, ast.ClassDef)), "<unknown>")
        offenders.extend(_module_state_writes(source, label))

    # Also sweep the component sources on disk. The index is what actually gets
    # exec'd, but it is a build artefact: editing a component without
    # regenerating it would otherwise leave this green until someone rebuilt the
    # index, which is exactly when the feedback is least useful.
    components_root = Path(lfx.__file__).resolve().parent / "components"
    on_disk = 0
    for path in sorted(components_root.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        if not any(isinstance(n, ast.ClassDef) for n in tree.body):
            continue
        on_disk += 1
        offenders.extend(_module_state_writes(source, path.relative_to(components_root).as_posix()))

    assert on_disk > 50, f"only {on_disk} on-disk component modules scanned; the sweep proves little"

    assert sorted(set(offenders)) == [], (
        f"component(s) write to module-level state, which a class cache turns into "
        f"worker-scoped shared state: {sorted(set(offenders))}"
    )


# ---------------------------------------------------------------------------
# connection pool
# ---------------------------------------------------------------------------


async def test_vertex_with_nothing_to_load_does_not_touch_the_connection_pool():
    """Guards the early return in ``update_params_with_load_from_db_fields``.

    ``get_instance_results`` runs it for every vertex, and most vertices have no
    load-from-db fields. Opening the session first took a pool checkout per
    vertex -- with ``pool_pre_ping`` on, a SELECT 1 round trip -- to do nothing.
    """
    from lfx.interface.initialize import loading

    opened = 0
    real_scope = loading.session_scope_readonly

    def counting_scope(*args, **kwargs):
        nonlocal opened
        opened += 1
        return real_scope(*args, **kwargs)

    loading.session_scope_readonly = counting_scope
    try:
        params = {"a": 1}
        result = await loading.update_params_with_load_from_db_fields(None, params, [])
    finally:
        loading.session_scope_readonly = real_scope

    assert result == params, "params must be returned untouched"
    assert opened == 0, f"opened {opened} session(s) for a vertex with nothing to load"
