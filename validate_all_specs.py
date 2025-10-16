#!/usr/bin/env python3
"""
Validate all specifications in the library using SpecService.
"""
import sys
import os
import asyncio
import yaml
from pathlib import Path

# Add the backend to Python path
sys.path.insert(0, str(Path(__file__).parent / "src" / "backend" / "base"))

from langflow.services.spec.service import SpecService

async def validate_all_specifications():
    """Validate all specifications and report results."""
    spec_service = SpecService()
    specs_dir = Path("src/backend/base/langflow/specifications_library/agents")

    # Find all YAML files
    yaml_files = list(specs_dir.rglob("*.yaml"))
    print(f"Found {len(yaml_files)} specification files\n")

    # Validate each specification
    validation_results = {}
    total_errors = 0
    total_warnings = 0
    failed_specs = []
    passed_specs = []

    for yaml_file in yaml_files:
        try:
            spec_content = yaml_file.read_text()

            # Validate using SpecService
            result = await spec_service.validate_spec(spec_content, detailed=True)

            relative_path = str(yaml_file.relative_to(specs_dir))
            validation_results[relative_path] = {
                'valid': result['valid'],
                'errors': len(result.get('errors', [])),
                'warnings': len(result.get('warnings', [])),
                'error_details': result.get('errors', [])[:3],  # Show first 3 errors
                'warning_details': result.get('warnings', [])[:3]  # Show first 3 warnings
            }

            total_errors += len(result.get('errors', []))
            total_warnings += len(result.get('warnings', []))

            status = '✅ PASS' if result['valid'] else '❌ FAIL'
            print(f"{status} {relative_path}")
            print(f"   Errors: {len(result.get('errors', []))}, Warnings: {len(result.get('warnings', []))}")

            if result['valid']:
                passed_specs.append(relative_path)
            else:
                failed_specs.append(relative_path)
                # Show some error details
                for i, error in enumerate(result.get('errors', [])[:2]):
                    if isinstance(error, dict):
                        print(f"   Error {i+1}: {error.get('message', str(error))}")
                    else:
                        print(f"   Error {i+1}: {error}")

            print()

        except Exception as e:
            validation_results[str(yaml_file)] = {'error': str(e)}
            print(f"❌ EXCEPTION {yaml_file.name}: {e}\n")
            failed_specs.append(str(yaml_file))

    # Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total specifications: {len(yaml_files)}")
    print(f"Passed: {len(passed_specs)}")
    print(f"Failed: {len(failed_specs)}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")

    if failed_specs:
        print(f"\nFailed specifications:")
        for spec in failed_specs:
            print(f"  - {spec}")

    return validation_results

if __name__ == "__main__":
    asyncio.run(validate_all_specifications())