"""Test to ensure all lfx component modules are importable.

This test validates that every component module in lfx.components can be imported
successfully without errors. It catches issues like:
- Deprecated import paths (e.g., langchain.embeddings.base -> langchain_core.embeddings)
- Missing dependencies
- Syntax errors
- Circular imports

This test is crucial for catching component import failures early in CI/CD.
"""

import asyncio
import importlib
import pkgutil

import pytest


class TestLfxComponentsImportable:
    """Test that all lfx.components modules are importable."""

    def test_all_component_categories_discoverable(self):
        """Test that all component categories can be discovered."""
        try:
            import lfx.components as components_pkg
        except ImportError as e:
            pytest.fail(f"Failed to import lfx.components package: {e}")

        # Get all top-level component categories
        categories = []
        for _, modname, _ispkg in pkgutil.iter_modules(components_pkg.__path__):
            if not modname.startswith("_"):  # Skip private modules
                categories.append(modname)

        assert len(categories) > 0, "No component categories found"

    @pytest.mark.asyncio
    async def test_all_component_modules_importable(self):
        """Test that all component modules can be imported without errors.

        This is the main test that catches import errors like deprecated imports,
        missing dependencies, etc. It walks through all modules in lfx.components
        and attempts to import them in parallel for faster execution.
        """
        try:
            import lfx.components as components_pkg
        except ImportError as e:
            pytest.fail(f"Failed to import lfx.components package: {e}")

        # Collect all module names first
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
                f"Failed imports:\n" + "\n".join(f"  • {f}" for f in failed_imports)
            )
            pytest.fail(
                failure_msg + "\n\n"
                f"Failed to import {len(failed_imports)} component modules. "
                "This may indicate deprecated imports, syntax errors, or other issues."
            )

    @pytest.mark.asyncio
    async def test_component_classes_instantiable(self):
        """Test that component classes from key modules can be instantiated.

        This test verifies that not only can modules be imported, but their
        component classes can also be instantiated (which triggers additional
        validation). Uses async for parallel testing.
        """
        # Test a sample of components from different categories
        test_cases = [
            ("lfx.components.data", "APIRequestComponent"),
            ("lfx.components.input_output", "ChatInput"),
            ("lfx.components.input_output", "ChatOutput"),
            ("lfx.components.processing", "ParseDataComponent"),
        ]

        async def test_instantiation(module_name, class_name):
            """Test instantiation of a single component."""
            try:
                # Import and instantiate in thread pool
                def _instantiate():
                    module = importlib.import_module(module_name)
                    component_class = getattr(module, class_name)
                    instance = component_class()

                    # Verify it has expected attributes
                    assert instance is not None
                    assert hasattr(instance, "display_name")
                    assert hasattr(instance, "description")

                await asyncio.to_thread(_instantiate)
            except ImportError:
                # Module import failed - this is caught by other tests
                return ("skipped", module_name, class_name, "import failed")
            except AttributeError as e:
                if "Could not import" in str(e):
                    # Missing dependency - expected for some components
                    return ("skipped", module_name, class_name, "missing dependency")
                return ("failed", module_name, class_name, str(e))
            except Exception as e:
                return ("failed", module_name, class_name, f"{type(e).__name__}: {e}")
            else:
                return ("success", module_name, class_name, None)

        # Test all components in parallel
        results = await asyncio.gather(*[test_instantiation(mod, cls) for mod, cls in test_cases])

        # Process results
        failed_instantiations = []
        for status, module_name, class_name, error in results:
            if status == "failed":
                failed_instantiations.append(f"{module_name}.{class_name}: {error}")

        if failed_instantiations:
            pytest.fail(f"Failed to instantiate components: {failed_instantiations}")

    def test_no_deprecated_langchain_imports(self):
        """Test that no component uses deprecated langchain import paths.

        This specifically catches the issue we fixed in Qdrant where
        'from langchain.embeddings.base import Embeddings' was used instead of
        'from langchain_core.embeddings import Embeddings'.
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
                # Skip files that can't be parsed - logging would be noisy for test files
                continue

        if deprecated_imports:
            failure_msg = (
                f"Found {len(deprecated_imports)} deprecated langchain imports.\n\n"
                f"Deprecated imports:\n" + "\n".join(f"  • {imp}" for imp in deprecated_imports)
            )
            pytest.fail(
                failure_msg + "\n\n"
                f"Found {len(deprecated_imports)} deprecated langchain imports. "
                "Please update to use current import paths."
            )

    def test_component_index_matches_actual_components(self):
        """Test that the prebuilt component index matches actual components.

        This ensures the component index is up-to-date and includes all components.
        """
        try:
            from pathlib import Path

            import orjson

            import lfx

            lfx_path = Path(lfx.__file__).parent
            index_path = lfx_path / "_assets" / "component_index.json"

            if not index_path.exists():
                pytest.skip("Component index not found")

            # Load the index
            index_data = orjson.loads(index_path.read_bytes())
            indexed_categories = {cat for cat, _ in index_data.get("entries", [])}

            # Get actual component categories
            import lfx.components as components_pkg

            actual_categories = set()
            for _, modname, _ispkg in pkgutil.iter_modules(components_pkg.__path__):
                if not modname.startswith("_") and "deactivated" not in modname:
                    actual_categories.add(modname)

            # Check for missing categories in index
            missing_in_index = actual_categories - indexed_categories
            if missing_in_index:
                pytest.fail(
                    f"Component index is out of date. "
                    f"Missing categories: {missing_in_index}. "
                    f"Component index is out of date. Missing categories: {missing_in_index}. "
                    "Run 'python scripts/build_component_index.py' to rebuild."
                )

        except ImportError:
            pytest.skip("Required packages not available")


class TestSpecificComponentImports:
    """Test specific components that have had import issues in the past."""

    def test_qdrant_component_importable(self):
        """Test that Qdrant component can be imported (regression test for deprecated import fix)."""
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

    @pytest.mark.asyncio
    async def test_vector_store_components_importable(self):
        """Test that all vector store components can be imported in parallel."""
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
        skipped_imports = []

        for status, module_name, class_name, error in results:
            if status == "failed":
                failed_imports.append(f"{module_name}.{class_name}: {error}")
            elif status == "skipped":
                skipped_imports.append(f"{module_name}.{class_name} ({error})")

        if failed_imports:
            failure_msg = (
                f"Failed to import {len(failed_imports)} vector store components.\n\n"
                f"Failed imports:\n" + "\n".join(f"  • {f}" for f in failed_imports)
            )
            pytest.fail(failure_msg)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
