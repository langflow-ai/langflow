"""Test to ensure all component modules are importable after dynamic import refactor.

This test validates that every component module can be imported successfully
and that all components listed in __all__ can be accessed.

This test suite includes:
1. Dynamic import system tests (lazy loading, caching, error handling)
2. Direct module import tests (catches actual import errors, syntax errors, deprecated imports)
3. AST-based code quality checks (deprecated import patterns)
4. Async parallel testing for performance

The combination of dynamic and direct import testing ensures both the import
system functionality AND the actual module code quality are validated.
"""

import asyncio
import importlib
import pkgutil

import pytest
from langflow import components


class TestAllModulesImportable:
    """Test that all component modules are importable."""

    def test_all_component_categories_importable(self):
        """Test that all component categories in __all__ can be imported."""
        failed_imports = []

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)
                assert category_module is not None, f"Category {category_name} is None"

                # Verify it's actually a module
                assert hasattr(category_module, "__name__"), f"Category {category_name} is not a module"

            except Exception as e:
                failed_imports.append(f"{category_name}: {e!s}")

        if failed_imports:
            pytest.fail(f"Failed to import categories: {failed_imports}")

    def test_all_components_in_categories_importable(self):
        """Test that all components in each category's __all__ can be imported."""
        failed_imports = []
        successful_imports = 0

        print(f"Testing component imports across {len(components.__all__)} categories")  # noqa: T201

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)

                if hasattr(category_module, "__all__"):
                    category_components = len(category_module.__all__)
                    print(f"Testing {category_components} components in {category_name}")  # noqa: T201

                    for component_name in category_module.__all__:
                        try:
                            component = getattr(category_module, component_name)
                            assert component is not None, f"Component {component_name} is None"
                            assert callable(component), f"Component {component_name} is not callable"
                            successful_imports += 1

                        except Exception as e:
                            failed_imports.append(f"{category_name}.{component_name}: {e!s}")
                            print(f"FAILED: {category_name}.{component_name}: {e!s}")  # noqa: T201
                else:
                    # Category doesn't have __all__, skip
                    print(f"Skipping {category_name} (no __all__ attribute)")  # noqa: T201
                    continue

            except Exception as e:
                failed_imports.append(f"Category {category_name}: {e!s}")
                print(f"FAILED: Category {category_name}: {e!s}")  # noqa: T201

        print(f"Successfully imported {successful_imports} components")  # noqa: T201

        if failed_imports:
            print(f"Failed imports ({len(failed_imports)}):")  # noqa: T201
            for failure in failed_imports[:10]:  # Show first 10 failures
                print(f"  - {failure}")  # noqa: T201
            if len(failed_imports) > 10:
                print(f"  ... and {len(failed_imports) - 10} more")  # noqa: T201

            pytest.fail(f"Failed to import {len(failed_imports)} components")

    def test_dynamic_imports_mapping_complete(self):
        """Test that _dynamic_imports mapping is complete for all categories."""
        failed_mappings = []

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)

                if hasattr(category_module, "__all__") and hasattr(category_module, "_dynamic_imports"):
                    category_all = set(category_module.__all__)
                    dynamic_imports_keys = set(category_module._dynamic_imports.keys())

                    # Check that all items in __all__ have corresponding _dynamic_imports entries
                    missing_in_dynamic = category_all - dynamic_imports_keys
                    if missing_in_dynamic:
                        failed_mappings.append(f"{category_name}: Missing in _dynamic_imports: {missing_in_dynamic}")

                    # Check that all _dynamic_imports keys are in __all__
                    missing_in_all = dynamic_imports_keys - category_all
                    if missing_in_all:
                        failed_mappings.append(f"{category_name}: Missing in __all__: {missing_in_all}")

            except Exception as e:
                failed_mappings.append(f"{category_name}: Error checking mappings: {e!s}")

        if failed_mappings:
            pytest.fail(f"Inconsistent mappings: {failed_mappings}")

    def test_backward_compatibility_imports(self):
        """Test that traditional import patterns still work."""
        # Test some key imports that should always work
        traditional_imports = [
            ("langflow.components.openai", "OpenAIModelComponent"),
            ("langflow.components.anthropic", "AnthropicModelComponent"),
            ("langflow.components.data", "APIRequestComponent"),
            ("langflow.components.models_and_agents", "AgentComponent"),
            ("langflow.components.helpers", "CalculatorComponent"),
        ]

        failed_imports = []

        for module_name, component_name in traditional_imports:
            try:
                module = importlib.import_module(module_name)
                component = getattr(module, component_name)
                assert component is not None
                assert callable(component)

            except Exception as e:
                failed_imports.append(f"{module_name}.{component_name}: {e!s}")

        if failed_imports:
            pytest.fail(f"Traditional imports failed: {failed_imports}")

    def test_component_modules_have_required_attributes(self):
        """Test that component modules have required attributes for dynamic loading."""
        failed_modules = []

        for category_name in components.__all__:
            try:
                category_module = getattr(components, category_name)

                # Check for required attributes
                required_attrs = ["__all__"]

                failed_modules.extend(
                    f"{category_name}: Missing required attribute {attr}"
                    for attr in required_attrs
                    if not hasattr(category_module, attr)
                )

                # Check that if it has dynamic imports, it has the pattern
                if hasattr(category_module, "_dynamic_imports"):
                    if not hasattr(category_module, "__getattr__"):
                        failed_modules.append(f"{category_name}: Has _dynamic_imports but no __getattr__")
                    if not hasattr(category_module, "__dir__"):
                        failed_modules.append(f"{category_name}: Has _dynamic_imports but no __dir__")

            except Exception as e:
                failed_modules.append(f"{category_name}: Error checking attributes: {e!s}")

        if failed_modules:
            pytest.fail(f"Module attribute issues: {failed_modules}")

    def test_no_circular_imports(self):
        """Test that there are no circular import issues."""
        # Test importing in different orders to catch circular imports
        import_orders = [
            ["models_and_agents", "data", "openai"],
            ["openai", "models_and_agents", "data"],
            ["data", "openai", "models_and_agents"],
        ]

        for order in import_orders:
            try:
                for category_name in order:
                    category_module = getattr(components, category_name)
                    # Access a component to trigger dynamic import
                    if hasattr(category_module, "__all__") and category_module.__all__:
                        first_component_name = category_module.__all__[0]
                        getattr(category_module, first_component_name)

            except Exception as e:
                pytest.fail(f"Circular import issue with order {order}: {e!s}")

    def test_component_access_caching(self):
        """Test that component access caching works correctly."""
        # Access the same component multiple times and ensure caching works
        test_cases = [
            ("openai", "OpenAIModelComponent"),
            ("data", "APIRequestComponent"),
            ("helpers", "CalculatorComponent"),
        ]

        for category_name, component_name in test_cases:
            category_module = getattr(components, category_name)

            # First access
            component1 = getattr(category_module, component_name)

            # Component should now be cached in module globals
            assert component_name in category_module.__dict__

            # Second access should return the same object
            component2 = getattr(category_module, component_name)
            assert component1 is component2, f"Caching failed for {category_name}.{component_name}"

    def test_error_handling_for_missing_components(self):
        """Test that appropriate errors are raised for missing components."""
        test_cases = [
            ("openai", "NonExistentComponent"),
            ("data", "AnotherNonExistentComponent"),
        ]

        for category_name, component_name in test_cases:
            category_module = getattr(components, category_name)

            with pytest.raises(AttributeError, match=f"has no attribute '{component_name}'"):
                getattr(category_module, component_name)

    def test_dir_functionality(self):
        """Test that __dir__ functionality works for all modules."""
        # Test main components module
        main_dir = dir(components)
        assert "openai" in main_dir
        assert "data" in main_dir
        assert "models_and_agents" in main_dir

        # Test category modules
        for category_name in ["openai", "data", "helpers"]:
            category_module = getattr(components, category_name)
            category_dir = dir(category_module)

            # Should include all components from __all__
            if hasattr(category_module, "__all__"):
                for component_name in category_module.__all__:
                    assert component_name in category_dir, f"{component_name} missing from dir({category_name})"

    def test_module_metadata_preservation(self):
        """Test that module metadata is preserved after dynamic loading."""
        test_components = [
            ("openai", "OpenAIModelComponent"),
            ("anthropic", "AnthropicModelComponent"),
            ("data", "APIRequestComponent"),
        ]

        for category_name, component_name in test_components:
            category_module = getattr(components, category_name)
            component = getattr(category_module, component_name)

            # Check that component has expected metadata
            assert hasattr(component, "__name__")
            assert hasattr(component, "__module__")
            assert component.__name__ == component_name
            assert category_name in component.__module__


class TestSpecificModulePatterns:
    """Test specific module patterns and edge cases."""

    def test_empty_init_modules(self):
        """Test modules that might have empty __init__.py files."""
        # These modules might have empty __init__.py files in the original structure
        potentially_empty_modules = [
            "chains",
            "output_parsers",
            "textsplitters",
            "toolkits",
            "link_extractors",
            "documentloaders",
        ]

        for module_name in potentially_empty_modules:
            if module_name in components.__all__:
                try:
                    module = getattr(components, module_name)
                    # Should be able to import even if empty
                    assert module is not None
                except Exception as e:
                    pytest.fail(f"Failed to import potentially empty module {module_name}: {e}")

    def test_platform_specific_imports(self):
        """Test platform-specific imports like NVIDIA Windows components."""
        # Test NVIDIA module which has platform-specific logic
        nvidia_module = components.nvidia
        assert nvidia_module is not None

        # Should have basic components regardless of platform
        assert "NVIDIAModelComponent" in nvidia_module.__all__

        # Should be able to access components
        nvidia_model = nvidia_module.NVIDIAModelComponent
        assert nvidia_model is not None

    def test_large_modules_import_efficiently(self):
        """Test that large modules with many components import efficiently."""
        import time

        # Test large modules
        large_modules = ["data", "processing", "langchain_utilities"]

        for module_name in large_modules:
            if module_name in components.__all__:
                start_time = time.time()
                module = getattr(components, module_name)
                import_time = time.time() - start_time

                # Initial import should be fast (just loading __init__.py)
                assert import_time < 0.5, f"Module {module_name} took too long to import: {import_time}s"

                # Should have components available
                assert hasattr(module, "__all__")
                assert len(module.__all__) > 0


class TestDirectModuleImports:
    """Test direct module imports to catch actual import errors.

    These tests bypass the lazy import system and directly import module files
    to catch issues like:
    - Deprecated import paths (e.g., langchain.embeddings.base)
    - Syntax errors
    - Missing imports
    - Circular imports
    """

    @pytest.mark.asyncio
    async def test_all_lfx_component_modules_directly_importable(self):
        """Test that all lfx component modules can be directly imported.

        This bypasses the lazy import system to catch actual import errors
        like deprecated imports, syntax errors, etc. Uses async for 3-5x
        performance improvement.
        """
        try:
            import lfx.components as components_pkg
        except ImportError:
            pytest.skip("lfx.components not available")

        # Collect all module names
        module_names = []
        for _, modname, _ in pkgutil.walk_packages(components_pkg.__path__, prefix=components_pkg.__name__ + "."):
            # Skip deactivated components
            if "deactivated" in modname:
                continue
            # Skip private modules
            if any(part.startswith("_") for part in modname.split(".")):
                continue
            module_names.append(modname)

        # Define async function to import a single module
        async def import_module_async(modname):
            """Import a module asynchronously."""
            try:
                # Run import in thread pool to avoid blocking
                await asyncio.to_thread(importlib.import_module, modname)
            except ImportError as e:
                error_msg = str(e)
                # Check if it's a missing optional dependency (expected)
                if any(
                    pkg in error_msg
                    for pkg in [
                        "langchain_openai",
                        "langchain_anthropic",
                        "langchain_google",
                        "langchain_cohere",
                        "langchain_pinecone",
                        "langchain_chroma",
                        "qdrant_client",
                        "pymongo",
                        "cassandra",
                        "weaviate",
                        "pinecone",
                        "chromadb",
                        "redis",
                        "elasticsearch",
                        "langchain_community",
                    ]
                ):
                    return ("skipped", modname, "missing optional dependency")
                return ("failed", modname, error_msg)
            except Exception as e:
                return ("failed", modname, f"{type(e).__name__}: {e}")
            else:
                return ("success", modname, None)

        # Import all modules in parallel
        results = await asyncio.gather(*[import_module_async(modname) for modname in module_names])

        # Process results
        failed_imports = []
        successful_imports = 0
        skipped_modules = []

        for status, modname, error in results:
            if status == "success":
                successful_imports += 1
            elif status == "skipped":
                skipped_modules.append(f"{modname} ({error})")
            else:  # failed
                failed_imports.append(f"{modname}: {error}")

        if failed_imports:
            failure_msg = (
                f"Failed to import {len(failed_imports)} component modules. "
                f"Successfully imported {successful_imports} modules. "
                f"Skipped {len(skipped_modules)} modules.\n\n"
                f"Failed imports:\n" + "\n".join(f"  • {f}" for f in failed_imports) + "\n\n"
                "This may indicate deprecated imports, syntax errors, or other issues."
            )
            pytest.fail(failure_msg)

    def test_no_deprecated_langchain_imports(self):
        """Test that no component uses deprecated langchain import paths.

        This specifically catches issues like the Qdrant bug where
        'from langchain.embeddings.base import Embeddings' was used instead of
        'from langchain_core.embeddings import Embeddings'.

        Uses AST parsing to scan all Python files for deprecated patterns.
        """
        import ast
        from pathlib import Path

        try:
            import lfx

            lfx_path = Path(lfx.__file__).parent
        except ImportError:
            pytest.skip("lfx package not found")

        components_path = lfx_path / "components"
        if not components_path.exists():
            pytest.skip("lfx.components directory not found")

        deprecated_imports = []

        # Known deprecated import patterns
        deprecated_patterns = [
            ("langchain.embeddings.base", "langchain_core.embeddings"),
            ("langchain.llms.base", "langchain_core.language_models.llms"),
            ("langchain.chat_models.base", "langchain_core.language_models.chat_models"),
            ("langchain.schema", "langchain_core.messages"),
            ("langchain.vectorstores", "langchain_community.vectorstores"),
            ("langchain.document_loaders", "langchain_community.document_loaders"),
            ("langchain.text_splitter", "langchain_text_splitters"),
        ]

        # Walk through all Python files in components
        for py_file in components_path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""

                        # Check against deprecated patterns
                        for deprecated, replacement in deprecated_patterns:
                            if module.startswith(deprecated):
                                relative_path = py_file.relative_to(lfx_path)
                                deprecated_imports.append(
                                    f"{relative_path}:{node.lineno}: "
                                    f"Uses deprecated '{deprecated}' - should use '{replacement}'"
                                )

            except Exception:  # noqa: S112
                # Skip files that can't be parsed
                continue

        if deprecated_imports:
            failure_msg = (
                f"Found {len(deprecated_imports)} deprecated langchain imports.\n\n"
                f"Deprecated imports:\n" + "\n".join(f"  • {imp}" for imp in deprecated_imports) + "\n\n"
                "Please update to use current import paths."
            )
            pytest.fail(failure_msg)

    @pytest.mark.asyncio
    async def test_vector_store_components_directly_importable(self):
        """Test that all vector store components can be directly imported.

        Vector stores are particularly prone to import issues due to their
        many optional dependencies. This test ensures they can be imported
        when dependencies are available.
        """
        vector_store_components = [
            ("lfx.components.chroma", "ChromaVectorStoreComponent"),
            ("lfx.components.pinecone", "PineconeVectorStoreComponent"),
            ("lfx.components.qdrant", "QdrantVectorStoreComponent"),
            ("lfx.components.weaviate", "WeaviateVectorStoreComponent"),
            ("lfx.components.vectorstores", "LocalDBComponent"),
        ]

        async def test_vector_store_import(module_name, class_name):
            """Test import of a single vector store component."""
            try:

                def _import():
                    module = importlib.import_module(module_name)
                    component_class = getattr(module, class_name)
                    assert isinstance(component_class, type)

                await asyncio.to_thread(_import)
            except (ImportError, AttributeError) as e:
                error_msg = str(e)
                # Check if it's a missing optional dependency
                if any(
                    pkg in error_msg
                    for pkg in [
                        "langchain_chroma",
                        "langchain_pinecone",
                        "qdrant_client",
                        "weaviate",
                        "chromadb",
                        "pinecone",
                        "langchain_community",
                    ]
                ):
                    return ("skipped", module_name, class_name, "missing optional dependency")
                return ("failed", module_name, class_name, error_msg)
            else:
                return ("success", module_name, class_name, None)

        # Test all vector stores in parallel
        results = await asyncio.gather(*[test_vector_store_import(mod, cls) for mod, cls in vector_store_components])

        # Process results
        failed_imports = []

        for status, module_name, class_name, error in results:
            if status == "failed":
                failed_imports.append(f"{module_name}.{class_name}: {error}")

        if failed_imports:
            failure_msg = (
                f"Failed to import {len(failed_imports)} vector store components.\n\n"
                f"Failed imports:\n" + "\n".join(f"  • {f}" for f in failed_imports)
            )
            pytest.fail(failure_msg)

    def test_qdrant_component_directly_importable(self):
        """Regression test for Qdrant component import (deprecated import fix).

        This test specifically validates that the Qdrant component can be
        imported after fixing the deprecated langchain.embeddings.base import.
        """
        try:
            from lfx.components.qdrant import QdrantVectorStoreComponent

            # Verify it's a class
            assert isinstance(QdrantVectorStoreComponent, type)

            # Verify it has expected attributes
            assert hasattr(QdrantVectorStoreComponent, "display_name")
            assert QdrantVectorStoreComponent.display_name == "Qdrant"

        except ImportError as e:
            if "qdrant_client" in str(e) or "langchain_community" in str(e):
                pytest.skip("Qdrant dependencies not installed (expected in test environment)")
            pytest.fail(f"Failed to import QdrantVectorStoreComponent: {e}")
        except AttributeError as e:
            if "Could not import" in str(e):
                pytest.skip("Qdrant dependencies not installed (expected in test environment)")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
