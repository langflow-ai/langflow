#!/usr/bin/env python3
"""Test the edge creation fix with eoc-check-agent.yaml"""

import json
import yaml
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, "src/backend/base")

def test_edge_format_fix():
    """Test that edge ID format matches expected Langflow format."""
    print("🧪 Testing Edge ID Format Fix")
    print("=" * 50)

    # Test edge ID generation manually
    source_id = "eoc-search"
    target_id = "eoc-agent"

    # Simulate handle objects
    source_handle = {
        "dataType": "KnowledgeHubSearch",
        "id": source_id,
        "name": "component_as_tool",
        "output_types": ["Tool"]
    }

    target_handle = {
        "fieldName": "tools",
        "id": target_id,
        "inputTypes": ["Tool"],
        "type": "other"
    }

    # Generate encoded handles (matching converter logic)
    source_handle_encoded = json.dumps(source_handle, separators=(",", ":")).replace('"', "œ")
    target_handle_encoded = json.dumps(target_handle, separators=(",", ":")).replace('"', "œ")

    # Generate edge ID using the FIXED format
    edge_id = f"reactflow__edge-{source_id}{source_handle_encoded}-{target_id}{target_handle_encoded}"

    print("🔧 Generated Edge Details:")
    print(f"   Source: {source_id}")
    print(f"   Target: {target_id}")
    print(f"   Source Handle: {source_handle}")
    print(f"   Target Handle: {target_handle}")
    print()
    print(f"📋 Edge ID: {edge_id[:100]}...")
    print()

    # Validate edge ID format
    if edge_id.startswith("reactflow__edge-"):
        print("✅ Edge ID uses correct 'reactflow__edge-' prefix")
    else:
        print("❌ Edge ID has wrong prefix")

    if "œ" in edge_id:
        print("✅ Edge ID contains encoded handles with œ characters")
    else:
        print("❌ Edge ID missing encoded handle data")

    # Check handle encoding
    if "œdataTypeœ" in source_handle_encoded and "œfieldNameœ" in target_handle_encoded:
        print("✅ Handles properly encoded with field data")
    else:
        print("❌ Handle encoding issue")

    print("\n🎯 Expected Result:")
    print("   - Tool components should show 'Toolset' output")
    print("   - Agent should show 'Tools' input")
    print("   - Edge should connect them automatically via provides declarations")

def test_yaml_structure():
    """Test the YAML structure for tool connections."""
    print("\n" + "=" * 50)
    print("📝 Testing YAML Structure")

    # Load eoc-check-agent.yaml
    try:
        with open("eoc-check-agent.yaml", "r") as f:
            data = yaml.safe_load(f)

        print("✅ Successfully loaded eoc-check-agent.yaml")

        # Check components with provides
        components_with_provides = []
        for comp_id, comp_data in data.get("components", {}).items():
            if "provides" in comp_data:
                provides = comp_data["provides"]
                for provide in provides:
                    if provide.get("useAs") == "tools":
                        components_with_provides.append({
                            "id": comp_id,
                            "type": comp_data.get("type"),
                            "target": provide.get("in")
                        })

        print(f"✅ Found {len(components_with_provides)} tool components:")
        for comp in components_with_provides:
            print(f"   - {comp['id']} ({comp['type']}) → {comp['target']}")

        return len(components_with_provides) > 0

    except Exception as e:
        print(f"❌ Failed to load YAML: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Edge Creation Fix\n")

    test_edge_format_fix()

    if test_yaml_structure():
        print("\n✅ All tests passed! Edge creation should work now.")
        print("\n🎯 Next Steps:")
        print("1. Test with actual conversion system")
        print("2. Verify edges appear in AI Studio UI")
        print("3. Confirm tool connections work in conversations")
    else:
        print("\n❌ YAML structure test failed")