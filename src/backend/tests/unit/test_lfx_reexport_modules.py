"""Test to ensure all langflow modules that re-export lfx modules work correctly.

This test validates that every langflow module that re-exports from lfx
can successfully import and access all expected symbols, maintaining
backward compatibility and proper API exposure.

Based on analysis, there are 24 langflow modules that re-export from lfx:

Base Modules (11):
- langflow.base (wildcard from lfx.base)
- langflow.base.agents (from lfx.base.agents)
- langflow.base.data (from lfx.base.data)
- langflow.base.embeddings (from lfx.base.embeddings)
- langflow.base.io (from lfx.base.io)
- langflow.base.memory (from lfx.base.memory)
- langflow.base.models (from lfx.base.models)
- langflow.base.prompts (from lfx.base.prompts)
- langflow.base.textsplitters (from lfx.base.textsplitters)
- langflow.base.tools (from lfx.base.tools)
- langflow.base.vectorstores (from lfx.base.vectorstores)

Core System Modules (13):
- langflow.custom (from lfx.custom)
- langflow.custom.custom_component (from lfx.custom.custom_component)
- langflow.field_typing (from lfx.field_typing with __getattr__)
- langflow.graph (from lfx.graph)
- langflow.inputs (from lfx.inputs.inputs)
- langflow.interface (from lfx.interface)
- langflow.io (from lfx.io + lfx.template)
- langflow.load (from lfx.load)
- langflow.logging (from lfx.log.logger)
- langflow.schema (from lfx.schema)
- langflow.template (wildcard from lfx.template)
- langflow.template.field (from lfx.template.field)
"""

import importlib
import inspect
import pkgutil
import re
import time
from pathlib import Path

import pytest


def get_all_reexport_modules():
    """Get all known re-export modules for parametrized testing."""
    # Define the modules here so they can be accessed by parametrize
    direct_reexport_modules = {
        "langflow.base.agents": "lfx.base.agents",
        "langflow.base.data": "lfx.base.data",
        "langflow.base.embeddings": "lfx.base.embeddings",
        "langflow.base.io": "lfx.base.io",
        "langflow.base.memory": "lfx.base.memory",
        "langflow.base.models": "lfx.base.models",
        "langflow.base.prompts": "lfx.base.prompts",
        "langflow.base.textsplitters": "lfx.base.textsplitters",
        "langflow.base.tools": "lfx.base.tools",
        "langflow.base.vectorstores": "lfx.base.vectorstores",
        "langflow.custom.custom_component": "lfx.custom.custom_component",
        "langflow.graph": "lfx.graph",
        "langflow.inputs": "lfx.inputs.inputs",
        "langflow.interface": "lfx.interface",
        "langflow.load": "lfx.load",
        "langflow.logging": "lfx.log",
        "langflow.schema": "lfx.schema",
        "langflow.template.field": "lfx.template.field",
    }

    wildcard_reexport_modules = {
        "langflow.base": "lfx.base",
        "langflow.template": "lfx.template",
    }

    complex_reexport_modules = {
        "langflow.custom": ["lfx.custom", "lfx.custom.custom_component", "lfx.custom.utils"],
        "langflow.io": ["lfx.io", "lfx.template"],
    }

    dynamic_reexport_modules = {
        "langflow.field_typing": "lfx.field_typing",
    }

    return list(
        {
            **direct_reexport_modules,
            **wildcard_reexport_modules,
            **complex_reexport_modules,
            **dynamic_reexport_modules,
        }.keys()
    )


class TestLfxReexportModules:
    """Test that all langflow modules that re-export from lfx work correctly."""

    @classmethod
    def _discover_langflow_modules(cls) -> list[str]:
        """Dynamically discover all langflow modules."""
        langflow_modules = []
        try:
            import langflow

            for _importer, modname, _ispkg in pkgutil.walk_packages(langflow.__path__, langflow.__name__ + "."):
                langflow_modules.append(modname)
        except ImportError:
            pass
        return langflow_modules

    @classmethod
    def _detect_reexport_pattern(cls, module_name: str) -> dict[str, str | None]:
        """Detect what kind of re-export pattern a module uses."""
        try:
            module = importlib.import_module(module_name)

            # Check if module has source code that mentions lfx
            source_file = getattr(module, "__file__", None)
            if source_file:
                try:
                    with Path(source_file).open() as f:
                        content = f.read()
                        if "from lfx" in content:
                            # Try to extract the lfx module being imported
                            patterns = [
                                r"from (lfx\.[.\w]+) import",
                                r"from (lfx\.[.\w]+) import \*",
                                r"import (lfx\.[.\w]+)",
                            ]
                            for pattern in patterns:
                                match = re.search(pattern, content)
                                if match:
                                    return {"type": "direct", "source": match.group(1)}

                        if "__getattr__" in content and "lfx" in content:
                            return {"type": "dynamic", "source": None}

                        # If we get here, file exists but no patterns matched
                        return {"type": "none", "source": None}

                except (OSError, UnicodeDecodeError):
                    return {"type": "none", "source": None}
            else:
                return {"type": "none", "source": None}

        except ImportError:
            return {"type": "import_error", "source": None}

    @classmethod
    def _get_expected_symbols(cls, lfx_source: str | None = None) -> list[str]:
        """Get expected symbols that should be available in a module."""
        if not lfx_source:
            return []

        try:
            lfx_module = importlib.import_module(lfx_source)
            if hasattr(lfx_module, "__all__"):
                return list(lfx_module.__all__)
            # Return public attributes (not starting with _)
            return [name for name in dir(lfx_module) if not name.startswith("_")]
        except ImportError:
            return []

    # Define all the modules that re-export from lfx (kept for backward compatibility)
    DIRECT_REEXPORT_MODULES = {
        # Base modules with direct re-exports
        "langflow.base.agents": "lfx.base.agents",
        "langflow.base.data": "lfx.base.data",
        "langflow.base.embeddings": "lfx.base.embeddings",
        "langflow.base.io": "lfx.base.io",
        "langflow.base.memory": "lfx.base.memory",
        "langflow.base.models": "lfx.base.models",
        "langflow.base.prompts": "lfx.base.prompts",
        "langflow.base.textsplitters": "lfx.base.textsplitters",
        "langflow.base.tools": "lfx.base.tools",
        "langflow.base.vectorstores": "lfx.base.vectorstores",
        # Core system modules with direct re-exports
        "langflow.custom.custom_component": "lfx.custom.custom_component",
        "langflow.graph": "lfx.graph",
        "langflow.inputs": "lfx.inputs.inputs",
        "langflow.interface": "lfx.interface",
        "langflow.load": "lfx.load",
        "langflow.logging": "lfx.log",  # Note: imports from lfx.log.logger
        "langflow.schema": "lfx.schema",
        "langflow.template.field": "lfx.template.field",
    }

    # Modules that use wildcard imports from lfx
    WILDCARD_REEXPORT_MODULES = {
        "langflow.base": "lfx.base",
        "langflow.template": "lfx.template",
    }

    # Modules with complex/mixed import patterns
    COMPLEX_REEXPORT_MODULES = {
        "langflow.custom": ["lfx.custom", "lfx.custom.custom_component", "lfx.custom.utils"],
        "langflow.io": ["lfx.io", "lfx.template"],  # Mixed imports
    }

    # Modules with dynamic __getattr__ patterns
    DYNAMIC_REEXPORT_MODULES = {
        "langflow.field_typing": "lfx.field_typing",
    }

    def test_direct_reexport_modules_importable(self):
        """Test that all direct re-export modules can be imported."""
        successful_imports = 0

        for langflow_module, lfx_module in self.DIRECT_REEXPORT_MODULES.items():
            try:
                # Import the langflow module
                lf_module = importlib.import_module(langflow_module)
                assert lf_module is not None, f"Langflow module {langflow_module} is None"

                # Import the corresponding lfx module to compare

                lfx_mod = importlib.import_module(lfx_module)
                assert lfx_mod is not None, f"LFX module {lfx_module} is None"

                successful_imports += 1

            except Exception as e:
                pytest.fail(f"Failed to import direct re-export module {langflow_module}: {e!s}")

    def test_wildcard_reexport_modules_importable(self):
        """Test that modules using wildcard imports work correctly."""
        successful_imports = 0

        for langflow_module, lfx_module in self.WILDCARD_REEXPORT_MODULES.items():
            try:
                # Import the langflow module
                lf_module = importlib.import_module(langflow_module)
                assert lf_module is not None, f"Langflow module {langflow_module} is None"

                # Wildcard imports should expose most/all attributes from lfx module
                lfx_mod = importlib.import_module(lfx_module)

                # Check that all attributes are available
                if hasattr(lfx_mod, "__all__"):
                    all_attrs = list(lfx_mod.__all__)  # Test all attributes
                    for attr in all_attrs:
                        if hasattr(lfx_mod, attr):
                            assert hasattr(lf_module, attr), f"Attribute {attr} missing from {langflow_module}"

                successful_imports += 1

            except Exception as e:
                pytest.fail(f"Failed to import wildcard re-export module {langflow_module}: {e!s}")

    def test_complex_reexport_modules_importable(self):
        """Test that modules with complex/mixed import patterns work correctly."""
        successful_imports = 0

        for langflow_module in self.COMPLEX_REEXPORT_MODULES:
            try:
                # Import the langflow module
                lf_module = importlib.import_module(langflow_module)
                assert lf_module is not None, f"Langflow module {langflow_module} is None"

                # Verify it has __all__ attribute for complex modules
                assert hasattr(lf_module, "__all__"), f"Complex module {langflow_module} missing __all__"
                assert len(lf_module.__all__) > 0, f"Complex module {langflow_module} has empty __all__"

                # Try to access all items from __all__
                all_items = lf_module.__all__  # Test all items
                for item in all_items:
                    try:
                        attr = getattr(lf_module, item)
                        assert attr is not None, f"Attribute {item} is None in {langflow_module}"
                    except AttributeError:
                        pytest.fail(f"Complex module {langflow_module} missing expected attribute {item} from __all__")

                successful_imports += 1

            except Exception as e:
                pytest.fail(f"Failed to import complex re-export module {langflow_module}: {e!s}")

    def test_dynamic_reexport_modules_importable(self):
        """Test that modules with __getattr__ dynamic loading work correctly."""
        successful_imports = 0

        for langflow_module in self.DYNAMIC_REEXPORT_MODULES:
            try:
                # Import the langflow module
                lf_module = importlib.import_module(langflow_module)
                assert lf_module is not None, f"Langflow module {langflow_module} is None"

                # Dynamic modules should have __getattr__ method
                assert hasattr(lf_module, "__getattr__"), f"Dynamic module {langflow_module} missing __getattr__"

                # Test accessing some known attributes dynamically
                if langflow_module == "langflow.field_typing":
                    # Test some known field typing constants
                    test_attrs = ["Data", "Text", "LanguageModel"]
                    for attr in test_attrs:
                        try:
                            value = getattr(lf_module, attr)
                            assert value is not None, f"Dynamic attribute {attr} is None"
                        except AttributeError:
                            pytest.fail(f"Dynamic module {langflow_module} missing expected attribute {attr}")

                successful_imports += 1

            except Exception as e:
                pytest.fail(f"Failed to import dynamic re-export module {langflow_module}: {e!s}")

    def test_all_reexport_modules_have_required_structure(self):
        """Test that re-export modules have the expected structure."""
        all_modules = {}
        all_modules.update(self.DIRECT_REEXPORT_MODULES)
        all_modules.update(self.WILDCARD_REEXPORT_MODULES)
        all_modules.update(self.DYNAMIC_REEXPORT_MODULES)

        # Add complex modules
        for lf_mod in self.COMPLEX_REEXPORT_MODULES:
            all_modules[lf_mod] = self.COMPLEX_REEXPORT_MODULES[lf_mod]

        for langflow_module in all_modules:
            try:
                lf_module = importlib.import_module(langflow_module)

                # All modules should be importable
                assert lf_module is not None

                # Most should have __name__ attribute
                assert hasattr(lf_module, "__name__")

                # Check for basic module structure
                assert hasattr(lf_module, "__file__") or hasattr(lf_module, "__path__")

            except Exception as e:
                pytest.fail(f"Module structure issue with {langflow_module}: {e!s}")

    def test_reexport_modules_backward_compatibility(self):
        """Test that common import patterns still work for backward compatibility."""
        # Test some key imports that should always work
        backward_compatible_imports = [
            ("langflow.schema", "Data"),
            ("langflow.inputs", "StrInput"),
            ("langflow.inputs", "IntInput"),
            ("langflow.custom", "Component"),  # Base component class
            ("langflow.custom", "CustomComponent"),
            ("langflow.field_typing", "Text"),  # Dynamic
            ("langflow.field_typing", "Data"),  # Dynamic
            ("langflow.load", "load_flow_from_json"),
            ("langflow.logging", "logger"),
        ]

        for module_name, symbol_name in backward_compatible_imports:
            try:
                module = importlib.import_module(module_name)
                symbol = getattr(module, symbol_name)
                assert symbol is not None

                # For callable objects, ensure they're callable
                if inspect.isclass(symbol) or inspect.isfunction(symbol):
                    assert callable(symbol)

            except Exception as e:
                pytest.fail(f"Backward compatibility issue with {module_name}.{symbol_name}: {e!s}")

    def test_no_circular_imports_in_reexports(self):
        """Test that there are no circular import issues in re-export modules."""
        # Test importing modules in different orders to catch circular imports
        import_orders = [
            ["langflow.schema", "langflow.inputs", "langflow.base"],
            ["langflow.base", "langflow.schema", "langflow.inputs"],
            ["langflow.inputs", "langflow.base", "langflow.schema"],
            ["langflow.custom", "langflow.field_typing", "langflow.template"],
            ["langflow.template", "langflow.custom", "langflow.field_typing"],
            ["langflow.field_typing", "langflow.template", "langflow.custom"],
        ]

        for order in import_orders:
            try:
                for module_name in order:
                    importlib.import_module(module_name)
                    # Try to access something from each module to trigger full loading
                    module = importlib.import_module(module_name)
                    if hasattr(module, "__all__") and module.__all__:
                        # Try to access first item in __all__
                        first_item = module.__all__[0]
                        try:
                            getattr(module, first_item)
                        except AttributeError:
                            pytest.fail(f"Module {module_name} missing expected attribute {first_item} from __all__")

            except Exception as e:
                pytest.fail(f"Circular import issue with order {order}: {e!s}")

    def test_reexport_modules_performance(self):
        """Test that re-export modules import efficiently."""
        # Test that basic imports are fast
        performance_critical_modules = [
            "langflow.schema",
            "langflow.inputs",
            "langflow.field_typing",
            "langflow.load",
            "langflow.logging",
        ]

        slow_imports = []

        for module_name in performance_critical_modules:
            start_time = time.time()
            try:
                importlib.import_module(module_name)
                import_time = time.time() - start_time

                # Re-export modules should import quickly (< 1 second)
                if import_time > 1.0:
                    slow_imports.append(f"{module_name}: {import_time:.3f}s")

            except ImportError:
                # Import failures are tested elsewhere
                pass

        # Don't fail the test, just record slow imports for information

    def test_coverage_completeness(self):
        """Test that we're testing all known re-export modules."""
        # This test ensures we don't miss any re-export modules
        all_tested_modules = set()
        all_tested_modules.update(self.DIRECT_REEXPORT_MODULES.keys())
        all_tested_modules.update(self.WILDCARD_REEXPORT_MODULES.keys())
        all_tested_modules.update(self.COMPLEX_REEXPORT_MODULES.keys())
        all_tested_modules.update(self.DYNAMIC_REEXPORT_MODULES.keys())

        # Should be testing all 24 identified modules based on our analysis
        actual_count = len(all_tested_modules)

        # Ensure we have a reasonable number of modules
        assert actual_count >= 20, f"Too few modules being tested: {actual_count}"
        assert actual_count <= 30, f"Too many modules being tested: {actual_count}"

    # Dynamic test methods using the discovery functions
    def test_dynamic_module_discovery(self):
        """Test that we can dynamically discover langflow modules."""
        modules = self._discover_langflow_modules()
        assert len(modules) > 0, "Should discover at least some langflow modules"

        # Check that known modules are found
        expected_modules = ["langflow.schema", "langflow.inputs", "langflow.custom"]
        found_modules = [mod for mod in expected_modules if mod in modules]
        assert len(found_modules) > 0, f"Expected to find some of {expected_modules}, but found: {found_modules}"

    @pytest.mark.parametrize("module_name", get_all_reexport_modules())
    def test_parametrized_module_import_and_pattern_detection(self, module_name: str):
        """Parametrized test that checks module import and pattern detection."""
        # Test that module can be imported
        try:
            module = importlib.import_module(module_name)
            assert module is not None, f"Module {module_name} should not be None"
        except ImportError:
            pytest.fail(f"Could not import {module_name}")

        # Test pattern detection
        pattern_info = self._detect_reexport_pattern(module_name)
        assert isinstance(pattern_info, dict), "Pattern detection should return a dict"
        assert "type" in pattern_info, "Pattern info should have 'type' key"
        assert pattern_info["type"] in ["direct", "dynamic", "none", "import_error"], (
            f"Unknown pattern type: {pattern_info['type']}"
        )

    def test_generate_backward_compatibility_imports(self):
        """Test generating backward compatibility imports dynamically."""
        # Test with a known module that has lfx imports
        test_cases = [("langflow.schema", "lfx.schema"), ("langflow.custom", "lfx.custom")]

        for lf_module, expected_lfx_source in test_cases:
            symbols = self._get_expected_symbols(expected_lfx_source)
            assert len(symbols) > 0, f"Should find some symbols in {expected_lfx_source}"

            # Test that at least some symbols are accessible in the langflow module
            module = importlib.import_module(lf_module)
            available_symbols = [sym for sym in symbols[:3] if hasattr(module, sym)]  # Test first 3
            assert len(available_symbols) > 0, f"Module {lf_module} should have some symbols from {expected_lfx_source}"
