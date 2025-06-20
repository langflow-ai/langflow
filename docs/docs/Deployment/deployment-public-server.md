---
title: Deploy your Langflow server externally with ngrok
slug: /deployment-public-server
---

By default, Langflow isn't exposed to the public internet.
However, you can forward Langflow server traffic with a forwarding platform like [ngrok](https://ngrok.com/docs/getting-started/) or [zrok](https://docs.zrok.io/docs/getting-started).

The following procedure uses ngrok, but you can use any similar reverse proxy or forwarding platform.
This procedure also assumes that you're using the default Langflow listening address `http://localhost:7860` (`http://localhost:7868` if using Langflow for Desktop).

1. Sign up for an [ngrok account](https://dashboard.ngrok.com/signup).

2. [Install ngrok](https://ngrok.com/docs/getting-started/#1-install-ngrok).

3. Copy your [ngrok authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) and use it to authenticate your local ngrok server:

    ```bash
    ngrok config add-authtoken NGROK_TOKEN
    ```

    Replace `NGROK_TOKEN` with your ngrok authtoken.

4. Use ngrok to expose your Langflow server to the public internet:

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

## Shareable playground

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/{flow-id}` endpoint.

You can share this endpoint publicly using a sharing platform like [Ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).

If you're using **Datastax Langflow**, you can share the URL with any users within your **Organization**.