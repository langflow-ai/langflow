"""Test script demonstrating template_search functionality."""

from langflow.agentic.utils import (
    get_all_tags,
    get_template_by_id,
    get_templates_count,
    list_templates,
)


def main():
    """Demonstrate template search functionality."""
    # print("=" * 80)
    # print("Template Search Demo")
    # print("=" * 80)

    # # 1. Get total count
    # print(f"\nTotal templates: {get_templates_count()}")

    # # 2. Get all available tags
    # print("\nAvailable tags:")
    # tags = get_all_tags()
    # print(f"  {', '.join(tags)}")

    # # 3. Get basic info for all templates
    # print("\n" + "=" * 80)
    # print("All Templates (ID, Name, Description)")
    # print("=" * 80)
    # templates = search_templates(fields=["id", "name", "description"])
    # for template in templates[:5]:  # Show first 5
    #     print(f"\nID: {template.get('id')}")
    #     print(f"Name: {template.get('name')}")
    #     print(f"Description: {template.get('description')}")

    # print(f"\n... and {len(templates) - 5} more templates")

    # # 4. Search for specific templates
    # print("\n" + "=" * 80)
    # print("Search: Templates containing 'agent'")
    # print("=" * 80)
    # agent_templates = search_templates(
    #     search_query="agent",
    #     fields=["name", "description", "tags"]
    # )
    # for template in agent_templates[:3]:
    #     print(f"\nName: {template.get('name')}")
    #     print(f"Description: {template.get('description')}")
    #     print(f"Tags: {template.get('tags')}")

    # # 5. Filter by tags
    # print("\n" + "=" * 80)
    # print("Filter: Templates with 'chatbots' tag")
    # print("=" * 80)
    templates_results = list_templates(
        fields=["name", "description"]
    )
    for template in templates_results:
        print(f"\n- {template.get('name')}: {template.get('description')}")

    print(len(templates_results))
    print(get_templates_count())
    # 6. Get specific template by ID
    # print("\n" + "=" * 80)
    # print("Get Template by ID")
    # print("=" * 80)
    # # Use the first template's ID
    # if templates:
    #     first_id = templates[0].get("id")
    #     specific_template = get_template_by_id(
    #         first_id,
    #         fields=["name", "description", "tags"]
    #     )
    #     if specific_template:
    #         print(f"\nRetrieved template:")
    #         print(f"Name: {specific_template.get('name')}")
    #         print(f"Description: {specific_template.get('description')}")
    #         print(f"Tags: {specific_template.get('tags')}")

    # # 7. Advanced: Multiple tag filter
    # print("\n" + "=" * 80)
    # print("Filter: Templates with 'agents' OR 'rag' tags")
    # print("=" * 80)
    # advanced_templates = search_templates(
    #     tags=["agents", "rag"],
    #     fields=["name", "tags"]
    # )
    # for template in advanced_templates[:5]:
    #     print(f"- {template.get('name')}: {template.get('tags')}")

    # print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
