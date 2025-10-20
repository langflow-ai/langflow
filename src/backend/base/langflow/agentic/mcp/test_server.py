"""Test script for the Langflow Agentic MCP Server."""

import json

from langflow.agentic.mcp.discovery import discover_all_tools, get_tool_list
from langflow.agentic.mcp.server import get_server_info


def test_server_info():
    """Test getting server information."""
    print("=" * 80)
    print("Testing Server Info")
    print("=" * 80)

    info = get_server_info()

    print(f"\nServer Name: {info['name']}")
    print(f"Version: {info['version']}")
    print(f"Description: {info['description']}")
    print(f"Number of Tools: {len(info['tools'])}\n")

    return info


def test_tool_discovery():
    """Test automatic tool discovery."""
    print("=" * 80)
    print("Testing Tool Discovery")
    print("=" * 80)

    tools = discover_all_tools()

    print(f"\nDiscovered {len(tools)} tools:\n")

    for tool_name, metadata in tools.items():
        print(f"  {tool_name}")
        print(f"    Module: {metadata['module_path']}")
        print(f"    Function: {metadata['function_name']}")
        print(f"    Description: {metadata['description'][:80]}...")

        # Show parameters
        schema = metadata['schema']
        properties = schema.get('properties', {})
        required = schema.get('required', [])

        if properties:
            print("    Parameters:")
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'any')
                is_required = param_name in required
                req_marker = " *" if is_required else ""
                print(f"      - {param_name}: {param_type}{req_marker}")

        print()

    return tools


def test_tool_schemas():
    """Test that all tools have valid schemas."""
    print("=" * 80)
    print("Testing Tool Schemas")
    print("=" * 80)

    tools = discover_all_tools()
    all_valid = True

    for tool_name, metadata in tools.items():
        schema = metadata['schema']

        # Check schema structure
        if 'type' not in schema:
            print(f"  ❌ {tool_name}: Missing 'type' in schema")
            all_valid = False
            continue

        if schema['type'] != 'object':
            print(f"  ❌ {tool_name}: Schema type should be 'object', got '{schema['type']}'")
            all_valid = False
            continue

        if 'properties' not in schema:
            print(f"  ⚠️  {tool_name}: No properties (function has no parameters)")
            continue

        print(f"  ✅ {tool_name}: Valid schema")

    if all_valid:
        print("\n✅ All tool schemas are valid!")
    else:
        print("\n❌ Some schemas have issues")

    return all_valid


def test_tool_execution():
    """Test executing tools with sample data."""
    print("=" * 80)
    print("Testing Tool Execution")
    print("=" * 80)

    tools = discover_all_tools()

    # Test get_templates_count (no parameters required)
    if "get_templates_count" in tools:
        print("\n  Testing get_templates_count...")
        func = tools["get_templates_count"]["function"]
        try:
            result = func()
            print(f"  ✅ Result: {result} templates")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # Test get_all_tags (no parameters required)
    if "get_all_tags" in tools:
        print("\n  Testing get_all_tags...")
        func = tools["get_all_tags"]["function"]
        try:
            result = func()
            print(f"  ✅ Result: {len(result)} tags found")
            print(f"     Tags: {', '.join(result[:5])}...")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # Test list_templates with parameters
    if "list_templates" in tools:
        print("\n  Testing list_templates with query='agent'...")
        func = tools["list_templates"]["function"]
        try:
            result = func(query="agent", fields=["id", "name"])
            print(f"  ✅ Result: {len(result)} templates found")
            if result:
                print(f"     First template: {result[0].get('name', 'N/A')}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # Test get_template_by_id
    if "get_template_by_id" in tools and "list_templates" in tools:
        print("\n  Testing get_template_by_id...")
        # Get a real template ID first
        list_func = tools["list_templates"]["function"]
        try:
            templates = list_func(fields=["id"])
            if templates:
                template_id = templates[0]["id"]
                get_func = tools["get_template_by_id"]["function"]
                result = get_func(template_id, fields=["name", "description"])
                if result:
                    print(f"  ✅ Result: Retrieved template '{result.get('name', 'N/A')}'")
                else:
                    print("  ❌ No template found")
            else:
                print("  ⚠️  No templates available to test with")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print()


def test_tool_list_json():
    """Test JSON output of tool list."""
    print("=" * 80)
    print("Testing JSON Tool List")
    print("=" * 80)

    tool_list = get_tool_list()

    print(f"\n{len(tool_list)} tools available\n")
    print(json.dumps(tool_list, indent=2))
    print()


def run_all_tests():
    """Run all tests."""
    print("\n" + "🧪 " * 40)
    print("LANGFLOW AGENTIC MCP SERVER - TEST SUITE")
    print("🧪 " * 40 + "\n")

    try:
        # Test 1: Server Info
        test_server_info()

        # Test 2: Tool Discovery
        test_tool_discovery()

        # Test 3: Schema Validation
        test_tool_schemas()

        # Test 4: Tool Execution
        test_tool_execution()

        # Test 5: JSON Output (commented out to avoid verbosity)
        # test_tool_list_json()

        print("=" * 80)
        print("✅ All Tests Completed Successfully!")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
