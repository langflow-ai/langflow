---
title: Deploy your Langflow server using ngrok
slug: /deployment-public-server
---

By default, your Langflow server at `http://localhost:7860` isn't exposed to the public internet.
However, you can forward Langflow server traffic with a forwarding platform like [ngrok](https://ngrok.com/docs/getting-started/) or [zrok](https://docs.zrok.io/docs/getting-started) to make your server public.

This allows you to [deploy your MCP server externally](#deploy-your-mcp-server-externally), [serve API requests](#serve-api-requests), and [share your playground externally](#share-your-playground-externally).

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

## Deploy your MCP server externally

To deploy your Langflow MCP server with ngrok, do the following:

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

## Serve API requests

Your public Langflow server can serve [Langflow API](/api-reference-api-examples) requests.

To send requests to a public Langflow server's Langflow API endpoints, use the server's domain as the [base URL](/api-reference-api-examples#base-url) for your API requests.
For example:

```bash
curl -X POST \
  "$PUBLIC_SERVER_DOMAIN/api/v1/webhook/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{"data": "example-data"}'
```

When you create flows in your public Langflow server, the code snippets in the [**API access** pane](/concepts-publish) automatically use your public server's domain.

For example, when used in a script, the following code snippet calls an ngrok domain to trigger the specified flow (`d764c4b8...`):

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

For a demo of the Langflow API in a script, see the [Quickstart](/get-started-quickstart).

## Share your playground externally

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/{flow-id}` endpoint.
This allows you to share a public URL with another user that displays only your flow's Playground chat window.
They can interact with your flow's chat input and output and view the results without requiring a Langflow installation or API keys of their own.

To share your flow's **Playground** with another user, do the following:

1. From the **Workspace**, click **Share**, and then enable **Shareable Playground**.
2. Click **Shareable Playground** again to open the Playground in a new window.
This window's URL, such as `https://3f7c-73-64-93-151.ngrok-free.app/playground/d764c4b8-5cec-4c0f-9de0-4b419b11901a`, is the address to share your Playground.
3. Share the URL with another user, and they can interact with your flow's Playground.