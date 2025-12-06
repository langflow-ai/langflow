import asyncio
import sys

# Try to import mcp, provide helpful error if missing
try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ImportError:
    print("Error: 'mcp' package not found.")
    print("Please install it using: pip install mcp")
    sys.exit(1)

async def main():
    # The streamable HTTP endpoint URL for the specific project
    # Note: streamablehttp_client expects the base URL (without /sse)
    # It will automatically append /sse for SSE connection and use base URL for POST
    project_id = "2930c536-ef5e-41d4-980a-b98b6f1ccefe"
    base_url = "http://localhost:7860"
    streamable_url = f"{base_url}/api/v1/mcp/project/{project_id}/"
    
    print(f"Connecting to streamable HTTP endpoint: {streamable_url}")
    
    try:
        # Connect to the streamable HTTP endpoint
        # This works just like sse_client but uses the newer streamable HTTP transport
        async with streamablehttp_client(streamable_url) as (read, write, get_session_id):
            print("Connected to streamable HTTP transport.")
            
            # Initialize the MCP ClientSession
            async with ClientSession(read, write) as session:
                print("Initializing client session...")
                await session.initialize()
                print("Session initialized.")
                
                # Get the session ID if needed
                session_id = get_session_id()
                if session_id:
                    print(f"Session ID: {session_id}")
                
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
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
