"""
Integration tests for AUTPE-6205: Complete Component Discovery and Model Catalog System.

Tests verify:
1. All 400+ components are discovered
2. All 9 Autonomize model variants are registered
3. Model catalog API works correctly
4. Database population is complete
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "base"))

from langflow.services.component_mapping.enhanced_discovery import EnhancedComponentDiscovery
from langflow.services.model_catalog.service import ModelCatalogService


class TestComponentDiscovery:
    """Test enhanced component discovery."""

    def test_discovers_all_components(self):
        """Test that discovery finds 380+ components."""
        discovery = EnhancedComponentDiscovery()
        results = discovery.discover_all_components()

        assert results["total"] >= 380, f"Expected 380+ components, found {results['total']}"
        assert results["files_scanned"] >= 380, f"Expected to scan 380+ files, scanned {results['files_scanned']}"
        assert len(results["categories"]) >= 80, f"Expected 80+ categories, found {len(results['categories'])}"

        # Check for specific component types
        stats = results["statistics"]
        assert stats["characteristics"]["models"] >= 150, "Expected 150+ model components"
        assert stats["characteristics"]["tools"] >= 10, "Expected 10+ tool components"
        assert stats["characteristics"]["healthcare"] >= 15, "Expected 15+ healthcare components"

    def test_discovers_autonomize_model_variants(self):
        """Test that all Autonomize model variants are discovered."""
        discovery = EnhancedComponentDiscovery()
        results = discovery.discover_all_components()

        # Find Autonomize components
        autonomize_components = [
            c for c in results["components"]
            if "autonomize" in c.class_name.lower()
        ]

        # Should have at least 9 variants + 2 base components
        assert len(autonomize_components) >= 11, f"Expected 11+ Autonomize components, found {len(autonomize_components)}"

        # Check for specific text model variants
        text_models = [
            "AutonomizeModelComponent_ClinicalLLM",
            "AutonomizeModelComponent_ClinicalNoteClassifier",
            "AutonomizeModelComponent_CombinedEntityLinking",
            "AutonomizeModelComponent_CPTCode",
            "AutonomizeModelComponent_ICD-10Code",
            "AutonomizeModelComponent_RxNormCode",
        ]

        for model_name in text_models:
            found = any(c.class_name == model_name for c in autonomize_components)
            assert found, f"Missing text model variant: {model_name}"

        # Check for document model variants
        doc_models = [
            "AutonomizeDocumentModelComponent_SRFExtraction",
            "AutonomizeDocumentModelComponent_SRFIdentification",
            "AutonomizeDocumentModelComponent_LetterSplitModel",
        ]

        for model_name in doc_models:
            found = any(c.class_name == model_name for c in autonomize_components)
            assert found, f"Missing document model variant: {model_name}"

    def test_component_metadata_extraction(self):
        """Test that component metadata is properly extracted."""
        discovery = EnhancedComponentDiscovery()
        results = discovery.discover_all_components()

        # Check that components have metadata
        components_with_inputs = sum(1 for c in results["components"] if c.has_inputs)
        components_with_outputs = sum(1 for c in results["components"] if c.has_outputs)

        assert components_with_inputs >= 300, f"Expected 300+ components with inputs, found {components_with_inputs}"
        assert components_with_outputs >= 300, f"Expected 300+ components with outputs, found {components_with_outputs}"

        # Check for beta components
        beta_components = sum(1 for c in results["components"] if c.beta)
        assert beta_components >= 5, f"Expected some beta components, found {beta_components}"


class TestModelCatalog:
    """Test model catalog service."""

    def test_model_catalog_initialization(self):
        """Test that model catalog initializes with all models."""
        catalog = ModelCatalogService()
        catalog.initialize()

        # Get all models
        all_models = catalog.get_all_models()
        assert len(all_models) >= 9, f"Expected at least 9 models, found {len(all_models)}"

        # Check for Autonomize models
        autonomize_models = catalog.get_all_models(filter_by_provider="autonomize")
        assert len(autonomize_models) == 9, f"Expected exactly 9 Autonomize models, found {len(autonomize_models)}"

        # Check text vs document models
        text_models = [m for m in autonomize_models if m.type == "text"]
        doc_models = [m for m in autonomize_models if m.type == "document"]

        assert len(text_models) == 6, f"Expected 6 text models, found {len(text_models)}"
        assert len(doc_models) == 3, f"Expected 3 document models, found {len(doc_models)}"

    def test_model_catalog_search(self):
        """Test model catalog search functionality."""
        catalog = ModelCatalogService()
        catalog.initialize()

        # Search for clinical models
        clinical_results = catalog.search_models("clinical")
        assert len(clinical_results) >= 2, f"Expected at least 2 clinical models, found {len(clinical_results)}"

        # Search for ICD models
        icd_results = catalog.search_models("icd")
        assert len(icd_results) >= 1, f"Expected at least 1 ICD model, found {len(icd_results)}"

        # Search for SRF models
        srf_results = catalog.search_models("srf")
        assert len(srf_results) >= 2, f"Expected at least 2 SRF models, found {len(srf_results)}"

    def test_model_catalog_capabilities(self):
        """Test model catalog capability filtering."""
        catalog = ModelCatalogService()
        catalog.initialize()

        # Get models with entity extraction capability
        entity_models = catalog.get_models_by_capability("entity_extraction")
        assert len(entity_models) >= 1, "Expected at least 1 model with entity extraction"

        # Get models with image analysis capability
        image_models = catalog.get_models_by_capability("image_analysis")
        assert len(image_models) >= 2, "Expected at least 2 models with image analysis"

        # Get healthcare compliant models
        healthcare_models = catalog.get_healthcare_compliant_models()
        assert len(healthcare_models) >= 9, f"Expected at least 9 healthcare models, found {len(healthcare_models)}"

    def test_model_catalog_statistics(self):
        """Test model catalog statistics."""
        catalog = ModelCatalogService()
        catalog.initialize()

        stats = catalog.get_catalog_statistics()

        assert stats["total_models"] >= 9, f"Expected at least 9 total models, found {stats['total_models']}"
        assert "text" in stats["by_type"], "Expected text models in statistics"
        assert "document" in stats["by_type"], "Expected document models in statistics"
        assert stats["by_provider"]["autonomize"] == 9, "Expected exactly 9 Autonomize models"
        assert stats["healthcare_compliant"] >= 9, "Expected at least 9 healthcare compliant models"


class TestDatabaseMigration:
    """Test database migration data generation."""

    def test_migration_data_generation(self):
        """Test that migration data is properly generated."""
        discovery = EnhancedComponentDiscovery()
        results = discovery.discover_all_components()

        # Generate migration data
        migration_data = discovery.generate_database_migration_data()

        assert len(migration_data) == results["total"], f"Migration data count mismatch: {len(migration_data)} vs {results['total']}"

        # Check migration data structure
        for mapping in migration_data[:10]:  # Check first 10
            assert "genesis_type" in mapping, "Missing genesis_type in mapping"
            assert "component" in mapping, "Missing component in mapping"
            assert "module_path" in mapping, "Missing module_path in mapping"
            assert "category" in mapping, "Missing category in mapping"
            assert "metadata" in mapping, "Missing metadata in mapping"

        # Check for Autonomize variants in migration data
        autonomize_mappings = [
            m for m in migration_data
            if "autonomize" in m["genesis_type"]
        ]
        assert len(autonomize_mappings) >= 11, f"Expected 11+ Autonomize mappings, found {len(autonomize_mappings)}"


def run_tests():
    """Run all tests and report results."""
    print("=" * 80)
    print("AUTPE-6205 Implementation Tests")
    print("=" * 80)

    test_classes = [
        TestComponentDiscovery(),
        TestModelCatalog(),
        TestDatabaseMigration(),
    ]

    total_passed = 0
    total_failed = 0
    failures = []

    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{class_name}:")
        print("-" * 40)

        # Get all test methods
        test_methods = [
            method for method in dir(test_class)
            if method.startswith("test_")
        ]

        for method_name in test_methods:
            try:
                method = getattr(test_class, method_name)
                method()
                print(f"✅ {method_name}")
                total_passed += 1
            except AssertionError as e:
                print(f"❌ {method_name}: {e}")
                failures.append(f"{class_name}.{method_name}: {e}")
                total_failed += 1
            except Exception as e:
                print(f"💥 {method_name}: Unexpected error: {e}")
                failures.append(f"{class_name}.{method_name}: Unexpected error: {e}")
                total_failed += 1

    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print("\n🎉 All tests passed!")

    print("\n" + "=" * 80)
    print(f"AUTPE-6205 Implementation Status: {'COMPLETE ✅' if total_failed == 0 else 'INCOMPLETE ❌'}")
    print("=" * 80)

    return total_failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)