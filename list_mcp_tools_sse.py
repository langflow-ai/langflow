import asyncio
import sys

# Try to import mcp, provide helpful error if missing
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
except ImportError:
    print("Error: 'mcp' package not found.")
    print("Please install it using: pip install mcp")
    sys.exit(1)


async def main():
    # The SSE endpoint URL for the specific project
    # Note: The project ID 2930c536-ef5e-41d4-980a-b98b6f1ccefe was provided in the request
    sse_url = "http://localhost:7860/api/v1/mcp/project/2930c536-ef5e-41d4-980a-b98b6f1ccefe/sse"

    print(f"Connecting to SSE endpoint: {sse_url}")

    try:
        # Connect to the SSE endpoint
        async with sse_client(sse_url) as (read, write):
            print("Connected to SSE stream.")

            # Initialize the MCP ClientSession
            async with ClientSession(read, write) as session:
                print("Initializing client session...")
                await session.initialize()
                print("Session initialized.")

                # List available tools
                print("Listing tools...")
                result = await session.list_tools()

                # Display results
                if not result.tools:
                    print("No tools found.")
                else:
                    print(f"Found {len(result.tools)} tools:")
                    for tool in result.tools:
                        print(f"- {tool.name}: {tool.description}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
