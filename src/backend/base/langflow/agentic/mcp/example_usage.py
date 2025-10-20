"""Example usage of the Langflow Agentic MCP Server tools.

This script demonstrates how to use the MCP tool functions directly.
When used via MCP protocol, these would be called by AI assistants like Claude.
"""

from langflow.agentic.mcp.server import count_templates, get_template, list_all_tags, search_templates


def main():
    """Demonstrate MCP tool usage."""
    print("=" * 60)
    print("Langflow Agentic MCP Server - Example Usage")
    print("=" * 60)
    print()

    # Example 1: Count all templates
    print("1. Count Templates")
    print("-" * 60)
    count = count_templates()
    print(f"Total templates available: {count}")
    print()

    # Example 2: Get all tags
    print("2. List All Tags")
    print("-" * 60)
    tags = list_all_tags()
    print(f"Available tags ({len(tags)}):")
    for tag in tags:
        print(f"  - {tag}")
    print()

    # Example 3: Search for basic templates with specific fields
    print("3. Search Templates - Basic Query")
    print("-" * 60)
    basic_templates = search_templates(query="Basic", fields=["id", "name", "description", "tags"])
    print(f"Found {len(basic_templates)} templates containing 'Basic':")
    for template in basic_templates[:3]:  # Show first 3
        print(f"\n  ID: {template.get('id')}")
        print(f"  Name: {template.get('name')}")
        print(f"  Description: {template.get('description', 'N/A')[:80]}...")
        print(f"  Tags: {', '.join(template.get('tags', []))}")
    print()

    # Example 4: Search by tag
    print("4. Search Templates - By Tag")
    print("-" * 60)
    if tags:
        # Use the first tag for example
        example_tag = tags[0]
        tagged_templates = search_templates(tags=[example_tag], fields=["name", "tags"])
        print(f"Templates with tag '{example_tag}' ({len(tagged_templates)}):")
        for template in tagged_templates[:5]:  # Show first 5
            print(f"  - {template.get('name')}")
        print()

    # Example 5: Get specific template by ID
    print("5. Get Template by ID")
    print("-" * 60)
    all_templates = search_templates(fields=["id"])
    if all_templates:
        example_id = all_templates[0]["id"]
        template = get_template(template_id=example_id, fields=["id", "name", "description", "tags"])
        if template:
            print(f"Template Details:")
            print(f"  ID: {template.get('id')}")
            print(f"  Name: {template.get('name')}")
            print(f"  Description: {template.get('description', 'N/A')}")
            print(f"  Tags: {', '.join(template.get('tags', []))}")
        print()

    # Example 6: Advanced search - multiple tags
    print("6. Advanced Search - Multiple Tags")
    print("-" * 60)
    if len(tags) >= 2:
        # Use first two tags
        multi_tag_templates = search_templates(tags=tags[:2], fields=["name", "tags"])
        print(f"Templates with tags {tags[0]} OR {tags[1]} ({len(multi_tag_templates)}):")
        for template in multi_tag_templates[:5]:
            print(f"  - {template.get('name')} [{', '.join(template.get('tags', []))}]")
        print()

    # Example 7: Get all templates with minimal fields
    print("7. List All Templates (Names Only)")
    print("-" * 60)
    all_names = search_templates(fields=["name"])
    print(f"All {len(all_names)} templates:")
    for i, template in enumerate(all_names[:10], 1):  # Show first 10
        print(f"  {i}. {template.get('name')}")
    if len(all_names) > 10:
        print(f"  ... and {len(all_names) - 10} more")
    print()

    print("=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
