#!/usr/bin/env python3
"""Validation test to verify integration framework works correctly."""

import sys
from pathlib import Path

# Add the framework to path
framework_path = Path(__file__).parent
sys.path.insert(0, str(framework_path))


def validate_framework():
    """Validate core framework functionality."""
    try:
        # Test imports
        from examples.test_framework_demo import TestMockComponentExample
        from generators import ComponentTestGenerator

        print("✓ Framework imports successful")

        # Test generator functionality
        generator = ComponentTestGenerator()
        assert hasattr(generator, "generate_test_class")
        assert hasattr(generator, "test_templates")
        print("✓ Test generator functionality works")

        # Test basic framework functionality
        import asyncio

        test = TestMockComponentExample()
        test.setup_method()
        test.test_component_initialization()

        async def run_async_test():
            await test.test_component_basic_execution()

        asyncio.run(run_async_test())

        test.teardown_method()
        print("✓ Framework functionality test passed")

        return True

    except Exception as e:
        print(f"✗ Validation failed: {e}")
        return False


def main():
    """Run framework validation."""
    print("🔍 Validating Integration Test Framework")
    print("=" * 40)

    if validate_framework():
        print("\n🎉 Framework validation passed!")
        print("Ready for use with:")
        print("• Component and flow testing")
        print("• Test generation capabilities")
        print("• Async execution support")
    else:
        print("\n❌ Framework validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
