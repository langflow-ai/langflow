#!/usr/bin/env python3
"""Validate the Agent Builder specification using SpecService"""

import sys
import os
import asyncio

# Add the Langflow modules to Python path
sys.path.insert(0, '/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base')

from langflow.services.spec.service import SpecService

async def validate_agent_builder_spec():
    """Validate the Agent Builder specification"""

    # Read the specification file
    spec_path = '/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/agents/ai-studio/agent-builder.yaml'

    try:
        with open(spec_path, 'r') as f:
            spec_yaml = f.read()

        print("🔍 Validating Agent Builder specification...")
        print(f"📁 File: {spec_path}")
        print()

        # Create SpecService instance
        spec_service = SpecService()

        # Validate the specification
        validation_result = spec_service.validate_spec(spec_yaml)

        # Display results
        print("=" * 60)
        print("VALIDATION RESULTS")
        print("=" * 60)

        if validation_result["valid"]:
            print("✅ VALIDATION PASSED")
            print("   The Agent Builder specification is valid and ready for use!")
        else:
            print("❌ VALIDATION FAILED")
            print("   The specification has errors that need to be fixed.")

        print()

        # Show errors
        if validation_result["errors"]:
            print("🚨 ERRORS:")
            for i, error in enumerate(validation_result["errors"], 1):
                print(f"   {i}. {error}")
            print()

        # Show warnings
        if validation_result["warnings"]:
            print("⚠️  WARNINGS:")
            for i, warning in enumerate(validation_result["warnings"], 1):
                print(f"   {i}. {warning}")
            print()

        # Summary
        print("📊 SUMMARY:")
        print(f"   • Valid: {validation_result['valid']}")
        print(f"   • Errors: {len(validation_result['errors'])}")
        print(f"   • Warnings: {len(validation_result['warnings'])}")

        if validation_result["valid"]:
            print()
            print("🎉 The Agent Builder specification is ready for deployment!")
            print("   Next steps:")
            print("   1. Test the Agent Builder with sample conversations")
            print("   2. Deploy to development environment")
            print("   3. Gather user feedback and iterate")
        else:
            print()
            print("🔧 Please fix the errors above before proceeding.")

        return validation_result["valid"]

    except FileNotFoundError:
        print(f"❌ Error: Specification file not found at {spec_path}")
        return False
    except Exception as e:
        print(f"❌ Error validating specification: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(validate_agent_builder_spec())
    sys.exit(0 if success else 1)