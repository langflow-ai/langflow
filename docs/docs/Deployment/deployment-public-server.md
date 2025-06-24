---
title: Deploy your Langflow server using ngrok
slug: /deployment-public-server
---

By default, your Langflow server at `http://localhost:7860` isn't exposed to the public internet.
However, you can forward Langflow server traffic with a forwarding platform like [ngrok](https://ngrok.com/docs/getting-started/) or [zrok](https://docs.zrok.io/docs/getting-started) to make your server public.

The following procedure uses ngrok, but you can use any similar reverse proxy or forwarding platform.
This procedure also assumes that you're using the default Langflow listening address `http://localhost:7860`.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [ngrok installed](https://ngrok.com/docs/getting-started/#1-install-ngrok)
- [An ngrok authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)

## Expose your Langflow server with ngrok

1. Start Langflow.

    ```bash
    uv run langflow run
    ```

2. In another terminal window, copy your [ngrok authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) and use it to authenticate your local ngrok server:

    ```bash
    ngrok config add-authtoken NGROK_TOKEN
    ```

    Replace `NGROK_TOKEN` with your ngrok authtoken.

3. Use ngrok to expose your Langflow server to the public internet:

    ```bash
    ngrok http http://localhost:7860
    ```

    The ngrok session starts in your terminal and deploys an ephemeral domain with no authentication.
    To add authentication or deploy a static domain, see the [ngrok documentation](https://ngrok.com/docs/).


    The `Forwarding` row displays the forwarding address for your Langflow server:

    ```
    Forwarding https://94b1-76-64-171-14.ngrok-free.app -> http://localhost:7860
    ```

    The forwarding address is acting as a reverse proxy for your Langflow server.

4. Open the URL where ngrok is forwarding your local traffic, such as `https://94b1-76-64-171-14.ngrok-free.app`.

    Your Langflow server is now publicly available at this domain.

### Share your playground externally

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/{flow-id}` endpoint.

To share your flow's **Playground** with another user, do the following:

1. From the **Workspace**, click **Share**, and then enable **Shareable Playground**.
2. Click **Shareable Playground** again to open the Playground in a new window.
This window's URL, such as `https://3f7c-73-64-93-151.ngrok-free.app/playground/d764c4b8-5cec-4c0f-9de0-4b419b11901a`, is the address to share.
3. Share the URL with another user, and they can interact with your flow's Playground.

### Share your MCP server externally {#deploy-your-server-externally}

To share your Langflow MCP server with ngrok, do the following:

1. Select the Langflow project that contains the flows you want to serve as tools, and then click the **MCP Server** tab.

    Note that the code template now contains your ngrok forwarding address instead of the localhost address.
    ```json
    {
      "mcpServers": {
        "PROJECT_NAME": {
          "command": "uvx",
          "args": [
            "mcp-proxy",
            "https://3f7c-73-64-93-151.ngrok-free.app/api/v1/mcp/project/d764c4b8-5cec-4c0f-9de0-4b419b11901a/sse"
          ]
        }
      }
    }
    ```

2. Complete the steps in [Connect clients to Langflow's MCP server](/mcp-server#connect-clients-to-use-the-servers-actions) using the ngrok forwarding address.

    For more information, see [MCP server](/mcp-server).

### Serve API requests

To serve API requests from your public server's `/run` endpoint, do the following:

1. From the **Workspace**, click **Share**, and then click **API access**.

    The default code in the API access pane constructs a request with the Langflow server `url`, `headers`, and a `payload` of request data.
    The code snippets automatically include the `LANGFLOW_SERVER_ADDRESS` and `FLOW_ID` values for the flow, so the code templates now contain your ngrok forwarding address instead of the localhost address:

    ```python
    import requests

    url = "https://3f7c-73-64-93-151.ngrok-free.app/api/v1/run/d764c4b8-5cec-4c0f-9de0-4b419b11901a"  # The complete API endpoint URL for this flow

    # Request payload configuration
    payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": "Hello"
    }

    # Request headers
    headers = {
        "Content-Type": "application/json"
    }

    try:
        # Send API request
        response = requests.request("POST", url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        # Print response
        print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
    except ValueError as e:
        print(f"Error parsing response: {e}")
    ```

2. Copy the snippet, paste it in a script file, and then run the script to send the request.
If you are using the curl snippet, you can run the command directly in your terminal.

    A successful response indicates ngrok is externally serving your flow at the `/run` endpoint.
    To further integrate your flow into your application, see the [Quickstart](/get-started-quickstart).