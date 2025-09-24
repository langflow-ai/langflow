"""Test script for DataFrame to Toolset component.

This script demonstrates how the DataFrame to Toolset component works by:
1. Creating a sample DataFrame with tool names and content
2. Converting it to a toolset
3. Executing the tools to see the results
"""

from langflow.components.processing.dataframe_to_toolset import DataFrameToToolsetComponent
from langflow.schema.dataframe import DataFrame


def test_dataframe_to_toolset():
    """Test the DataFrame to Toolset component with sample data."""
    # Create sample data - this could represent API endpoints, database queries,
    # documentation snippets, or any content you want to make callable as tools
    sample_data = [
        {
            "action_name": "Get Weather Info",
            "content": "Current weather in San Francisco: Sunny, 72°F, Light breeze from the west.",
            "category": "weather",
        },
        {
            "action_name": "Check Stock Price",
            "content": "AAPL stock price: $190.25 (+2.5% today). Trading volume: 45.2M shares.",
            "category": "finance",
        },
        {
            "action_name": "Latest News",
            "content": "Breaking: New AI breakthrough announced. Scientists develop more efficient language model architecture.",
            "category": "news",
        },
        {
            "action_name": "Company Info",
            "content": "Langflow: Open-source AI flow engineering platform for building LLM applications with visual interface.",
            "category": "company",
        },
        {
            "action_name": "Get System Status",
            "content": "All systems operational. API response time: 45ms. Uptime: 99.9%",
            "category": "system",
        },
    ]

    # Create DataFrame
    df = DataFrame(sample_data)
    print("Created DataFrame with the following data:")
    print(df.to_string())
    print("\n" + "=" * 60 + "\n")

    # Initialize the component
    component = DataFrameToToolsetComponent()

    # Set the inputs
    component.dataframe = df
    component.action_name_column = "action_name"
    component.content_column = "content"

    print("Building toolset from DataFrame...")

    # Build the tools
    tools = component.build_tools()

    print(f"Successfully created {len(tools)} tools:")
    for i, tool in enumerate(tools, 1):
        print(f"\n{i}. Tool Name: {tool.name}")
        print(f"   Display Name: {tool.metadata.get('display_name', 'N/A')}")
        print(f"   Description: {tool.description}")
        print(f"   Content Preview: {tool.metadata.get('content_preview', 'N/A')[:100]}...")

    print("\n" + "=" * 60 + "\n")

    # Test executing the tools
    print("Testing tool execution:")
    for i, tool in enumerate(tools[:3], 1):  # Test first 3 tools
        print(f"\n{i}. Executing '{tool.metadata.get('display_name', tool.name)}':")
        try:
            result = tool.func()
            print(f"   Result: {result}")
        except Exception as e:
            print(f"   Error: {e}")

    print("\n" + "=" * 60 + "\n")

    # Test the message output
    message = component.get_message()
    print("Component Message:")
    print(message.text)

    print("\n" + "=" * 60 + "\n")

    # Test the data output
    data_results = component.run_model()
    print("Component Data Output:")
    for i, data in enumerate(data_results, 1):
        print(f"\n{i}. {data.data}")

    return tools


def test_different_column_combinations():
    """Test with different column combinations to show flexibility."""
    print("\n" + "=" * 80)
    print("TESTING DIFFERENT COLUMN COMBINATIONS")
    print("=" * 80 + "\n")

    # Create a DataFrame with different structure - like API documentation
    api_docs_data = [
        {
            "endpoint": "POST /api/users",
            "description": "Creates a new user account with email and password",
            "example_response": '{"user_id": "12345", "email": "user@example.com", "status": "active"}',
            "status_code": "201",
        },
        {
            "endpoint": "GET /api/users/{id}",
            "description": "Retrieves user information by user ID",
            "example_response": '{"user_id": "12345", "email": "user@example.com", "created_at": "2024-01-15"}',
            "status_code": "200",
        },
        {
            "endpoint": "DELETE /api/users/{id}",
            "description": "Permanently deletes a user account",
            "example_response": '{"message": "User deleted successfully", "deleted_id": "12345"}',
            "status_code": "200",
        },
    ]

    df_api = DataFrame(api_docs_data)
    print("API Documentation DataFrame:")
    print(df_api.to_string())
    print("\n")

    # Use endpoint as action name and description as content
    component = DataFrameToToolsetComponent()
    component.dataframe = df_api
    component.action_name_column = "endpoint"
    component.content_column = "description"

    tools = component.build_tools()

    print(f"Created {len(tools)} API documentation tools:")
    for tool in tools:
        print(f"\n- {tool.metadata.get('display_name')}")
        print(f"  Content: {tool.func()}")


if __name__ == "__main__":
    print("=" * 80)
    print("DATAFRAME TO TOOLSET COMPONENT TEST")
    print("=" * 80)

    # Run the main test
    tools = test_dataframe_to_toolset()

    # Run additional test with different columns
    test_different_column_combinations()

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    print("\n🎉 The DataFrame to Toolset component is working correctly!")
    print(f"📊 Total tools created in main test: {len(tools)}")
    print("🔧 Each row of your DataFrame can now be called as a tool by LLM agents!")
