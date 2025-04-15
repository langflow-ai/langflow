import sys
from ast import parse, NodeVisitor, ImportFrom
from importlib import util as import_util, import_module
from importlib.machinery import ModuleSpec
from os import path
from pkgutil import iter_modules
from typing import Any, List, Iterator

import pytest

def _is_test_module(module_name: str) -> bool:
    components = module_name.split(".")

    return len(components) >= 2 and components[1] == "tests"


def _is_package(module_spec: ModuleSpec) -> bool:
    return module_spec.origin is not None and module_spec.origin.endswith("__init__.py")


def _recurse_modules(module_name: str, ignore_tests: bool, packages_only: bool) -> Iterator[str]:
    if ignore_tests and _is_test_module(module_name):
        return

    module_spec = import_util.find_spec(module_name)

    if module_spec is not None and module_spec.origin is not None:
        if not (packages_only and not _is_package(module_spec)):
            yield module_name

        for child in iter_modules([path.dirname(module_spec.origin)]):
            if child.ispkg:
                yield from _recurse_modules(
                    f"{module_name}.{child.name}",
                    ignore_tests=ignore_tests,
                    packages_only=packages_only,
                )
            elif not packages_only:
                yield f"{module_name}.{child.name}"


class _ImportFromSourceChecker(NodeVisitor):
    def __init__(self, module: str):
        module_spec = import_util.find_spec(module)
        is_pkg = (
            module_spec is not None and module_spec.origin is not None and module_spec.origin.endswith("__init__.py")
        )

        self._module = module if is_pkg else ".".join(module.split(".")[:-1])
        self._top_level_module = self._module.split(".")[0]

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        # Check that there are no relative imports that attempt to read from a parent module. We've found that there
        # generally is no good reason to have such imports.
        if node.level >= 2:
            raise ValueError(
                f"Import in {self._module} attempts to import from parent module using relative import. Please "
                f"switch to absolute import instead."
            )

        # Figure out which module to import in the case where this is a...
        if node.level == 0:
            # (1) absolute import where a submodule is specified
            assert node.module is not None
            module_to_import: str = node.module
        elif node.module is None:
            # (2) relative import where no module is specified (ie: "from . import foo")
            module_to_import = self._module
        else:
            # (3) relative import where a submodule is specified (ie: "from .bar import foo")
            module_to_import = f"{self._module}.{node.module}"

        # We're only looking at imports of objects defined inside this top-level package
        if not module_to_import.startswith(self._top_level_module):
            return

        # Actually import the module and iterate through all the objects potentially exported by it.
        module = import_module(module_to_import)
        for alias in node.names:
            assert hasattr(module, alias.name)
            attr = getattr(module, alias.name)

            # For some objects (pretty much everything except for classes and functions), we are not able to figure
            # out which module they were defined in... in that case there's not much we can do here, since we cannot
            # easily figure out where we *should* be importing this from in the first place.
            if isinstance(attr, type) or callable(attr):
                attribute_module = attr.__module__
            else:
                continue

            # Figure out where we should be importing this class from, and assert that the *actual* import we found
            # matches the place we *should* import from.
            should_import_from = self._get_module_should_import(module_to_import=attribute_module)
            assert module_to_import == should_import_from, (
                f"Imported {alias.name} from {module_to_import}, which is not the public module where this object "
                f"is defined. Please import from {should_import_from} instead."
            )

    def _get_module_should_import(self, module_to_import: str) -> str:
        """
        This function figures out the correct import path for "module_to_import" from the "self._module" module in
        this instance. The trivial solution here would be to always just return "module_to_import", but we want
        to actually take into account the fact that some submodules can be "private" (ie: start with an "_"), in
        which case we should only import from them if self._module is internal to that private module.
        """
        module_components = module_to_import.split(".")
        result: List[str] = []

        for component in module_components:
            if component.startswith("_") and not self._module.startswith(".".join(result)):
                break
            result.append(component)

        return ".".join(result)


def _apply_visitor(module: str, visitor: NodeVisitor) -> None:
    module_spec = import_util.find_spec(module)
    assert module_spec is not None
    assert module_spec.origin is not None

    with open(module_spec.origin, "r") as source_file:
        ast = parse(source=source_file.read(), filename=module_spec.origin)

    visitor.visit(ast)


def _test_imports_from_source(module: str) -> None:
    _apply_visitor(module=module, visitor=_ImportFromSourceChecker(module))


def add_module_organization_tests(module_name: str) -> None:
    """
    This function dynamically generates a set of python tests which can be used to ensure that all modules follow
    the convention "classes and functions should always be imported from the module they are defined in (or the
    closest public module to that)".

    Let's say that you have a package "foo", and want to use this function. In that case, go into your test module
    (probably "foo.tests") and create a test file that imports and calls `add_module_organization_tests(__name__)`.
    Once this is defined, you can use pytest to run your tests, and note that a unique test has been generated for
    each file in your project. The tests will scan each file and look for cases of imports that do not follow the
    convention above. If the test finds any violations, it will error out with a message similar to:

    AssertionError: Imported Child from objects, which is not the public module where this object is defined. Please
        import from objects.child instead.
    """
    module_root = module_name.split(".")[0]
    setattr(
        sys.modules[module_name],
        "test_imports_from_source",
        pytest.mark.parametrize(
            "module",
            list(_recurse_modules(module_root, ignore_tests=True, packages_only=False)),
        )(_test_imports_from_source),
    )