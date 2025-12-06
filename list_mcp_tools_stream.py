import asyncio
import sys
import json
import uuid
from urllib.parse import urljoin

# Try to import httpx and httpx_sse
try:
    import httpx
    from httpx_sse import aconnect_sse
except ImportError:
    print("Error: 'httpx' or 'httpx-sse' package not found.")
    print("Please install them using: pip install httpx httpx-sse")
    sys.exit(1)

async def main():
    project_id = "2930c536-ef5e-41d4-980a-b98b6f1ccefe"
    base_url = "http://localhost:7860"
    sse_path = f"/api/v1/mcp/project/{project_id}/sse"
    sse_url = f"{base_url}{sse_path}"
    
    print(f"Connecting to SSE endpoint to establish session: {sse_url}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with aconnect_sse(client, "GET", sse_url) as event_source:
                print("SSE connection established.")
                
                # Wait for the 'endpoint' event which provides the POST URL with session_id
                post_url = None
                # State machine for MCP protocol
                # 0: Not started, 1: Sent initialize, 2: Sent initialized notification, 3: Sent tools/list
                state = 0
                
                print("Listening for SSE events...")
                async for sse in event_source.aiter_sse():
                    if sse.event == "endpoint":
                        endpoint_path = sse.data
                        post_url = urljoin(base_url, endpoint_path)
                        print(f"Received POST endpoint: {post_url}")
                        
                        # Step 1: Send initialize
                        print("Sending initialize request...")
                        init_payload = {
                            "jsonrpc": "2.0",
                            "id": 0,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05", # Use a recent version
                                "capabilities": {},
                                "clientInfo": {"name": "manual-client", "version": "1.0"}
                            }
                        }
                        asyncio.create_task(client.post(post_url, json=init_payload))
                        state = 1
                        
                    elif sse.event == "message":
                        msg = json.loads(sse.data)
                        
                        if state == 1 and msg.get("id") == 0:
                            # Step 2: Received initialize response
                            print("Received initialize response.")
                            if "error" in msg:
                                print(f"Initialization error: {msg['error']}")
                                return
                                
                            # Step 3: Send initialized notification
                            print("Sending initialized notification...")
                            notif_payload = {
                                "jsonrpc": "2.0",
                                "method": "notifications/initialized"
                            }
                            asyncio.create_task(client.post(post_url, json=notif_payload))
                            state = 2
                            
                            # Step 4: Send tools/list
                            print("Sending tools/list request...")
                            list_payload = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "tools/list"
                            }
                            asyncio.create_task(client.post(post_url, json=list_payload))
                            state = 3
                            
                        elif state == 3 and msg.get("id") == 1:
                            # Step 5: Received tools/list response
                            if "result" in msg:
                                print_tools(msg["result"])
                            elif "error" in msg:
                                print(f"Error listing tools: {msg['error']}")
                            return
                        
                        elif "method" in msg:
                            # Server requests/notifications (ping, etc)
                            pass
                        else:
                            # print(f"Ignored message: {msg}")
                            pass

    except Exception as e:
        print(f"An error occurred: {e}")

def print_tools(result):
    tools = result.get("tools", [])
    if not tools:
        print("No tools found.")
    else:
        print(f"Found {len(tools)} tools:")
        for tool in tools:
            name = tool.get("name", "Unknown")
            description = tool.get("description", "No description")
            print(f"- {name}: {description}")

if __name__ == "__main__":
    asyncio.run(main())
