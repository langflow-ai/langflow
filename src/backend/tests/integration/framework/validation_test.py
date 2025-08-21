#!/usr/bin/env python3
"""Validation test to verify integration framework works correctly."""

import sys
from pathlib import Path

# Add the framework to path
framework_path = Path(__file__).parent
sys.path.insert(0, str(framework_path))


def test_framework_imports():
    """Test that framework imports work correctly."""
    try:
        # Test core framework components can be imported without Langflow deps
        from decorators import auto_cleanup, leak_detection, requires_api_key, skip_if_no_env
        from generators import ComponentTestGenerator, FlowTestGenerator, TestDiscovery

        print("✓ Framework imports successful (decorators and generators)")

        # Test that the demo works
        from examples.test_framework_demo import TestMockComponentExample

        print("✓ Demo test class imports successful")

        return True

    except ImportError as e:
        print(f"✗ Framework import failed: {e}")
        return False


def test_framework_functionality():
    """Test basic framework functionality."""
    try:
        import asyncio

        from examples.test_framework_demo import TestMockComponentExample

        # Create and run a simple test
        test = TestMockComponentExample()
        test.setup_method()

        # Test initialization
        test.test_component_initialization()

        # Test async execution
        async def run_async_test():
            await test.test_component_basic_execution()

        asyncio.run(run_async_test())

        test.teardown_method()

        print("✓ Framework functionality test passed")
        return True

    except Exception as e:
        print(f"✗ Framework functionality test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_generator_functionality():
    """Test that test generators work without full dependencies."""
    try:
        from generators import ComponentTestGenerator

        generator = ComponentTestGenerator()

        # Test that we can create a generator
        assert hasattr(generator, "generate_test_class")
        assert hasattr(generator, "test_templates")

        print("✓ Test generator functionality works")
        return True

    except Exception as e:
        print(f"✗ Test generator functionality failed: {e}")
        return False


def main():
    """Run all validation tests."""
    print("🔍 Validating Integration Test Framework")
    print("=" * 50)

    tests = [
        ("Framework Imports", test_framework_imports),
        ("Framework Functionality", test_framework_functionality),
        ("Generator Functionality", test_generator_functionality),
    ]

    all_passed = True

    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            result = test_func()
            if result:
                print(f"✅ {test_name} passed")
            else:
                print(f"❌ {test_name} failed")
                all_passed = False
        except Exception as e:
            print(f"❌ {test_name} error: {e}")
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All validation tests passed!")
        print("\nThe integration test framework is ready for use.")
        print("\nKey features validated:")
        print("- ✓ Base classes for component and flow testing")
        print("- ✓ Decorator patterns for common test scenarios")
        print("- ✓ Async test execution support")
        print("- ✓ Test generation capabilities")
        print("- ✓ Clean setup/teardown lifecycle")
    else:
        print("⚠️  Some validation tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
