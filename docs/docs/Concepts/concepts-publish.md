---
title: Publish flows
slug: /concepts-publish
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import ChatWidget from '@site/src/components/ChatWidget';

Langflow provides several ways to publish and integrate your flows into external applications. Whether you want to expose your flow as an API endpoint, embed it as a chat widget in your website, or share it as a public playground, this guide covers the options available for making your flows accessible to users.

## API access

The **API access** pane presents code templates for integrating your flow into external applications.

As of Langflow version 1.5, all API requests require authentication with a Langflow API key, even if `AUTO_LOGIN` is set to `True`.

<details>
<summary>Need help creating an API key?</summary>

To generate an API key to use with Langflow, do the following.

1. Open the Langflow UI, click your user icon, and then select **Settings**.
2. Click **Langflow API Keys**, and then click **Add New**.
3. Name your key, and then click **Create API Key**.
4. Copy the API key and store it in a secure location.
5. Use your Langflow API key in your API requests. For example:
    ```text
    curl --request POST \
     --url "http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID" \
     --header "Content-Type: application/json" \
     --header "x-api-key: LANGFLOW_API_KEY" \
     --data '{
       "output_type": "chat",
       "input_type": "chat",
       "input_value": "Hello"
     }'
    ```
Alternatively, the API pane's code snippets include a script to detect your local `LANGFLOW_API_KEY`.
To set this variable in your terminal:
```bash
export LANGFLOW_API_KEY="sk..."
```
</details>

![](/img/api-pane.png)

<Tabs>

<TabItem value="Python" label="Python">

The **Python** tab displays code to interact with your flow using the Python `requests` library.

1. Copy and paste the code into a Python script.
2. Run the script.

```python
python3 python-test-script.py --message="tell me about something interesting"
```

The response content depends on your flow. Make sure the endpoint returns a successful response.

</TabItem>

<TabItem value="JavaScript" label="JavaScript" default>

The **JavaScript API** tab displays code to interact with your flow in JavaScript.

1. Copy and paste the code into a JavaScript file.
2. Run the script.

```text
node test-script.js "tell me about something interesting"
```

The response content depends on your flow. Make sure the endpoint returns a successful response.

</TabItem>
<TabItem value="curl" label="curl" default>

The **cURL** tab displays sample code for posting a query to your flow.

Copy the code and run it to post a query to your flow and get the result.

The response content depends on your flow. Make sure the endpoint returns a successful response.

</TabItem>
</Tabs>

### Temporary overrides

The **Temporary overrides** tab displays the available parameters for your flow.
Modifying the parameters changes the code parameters across all windows.
For example, changing the **Chat Input** component's `input_value` changes that value across all API calls to the `/run` endpoint of this flow.

### Send files to your flow with the API

For information on sending files to the Langflow API, see [Files endpoint](/api-files).

## Shareable playground

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/$FLOW_ID` endpoint.

You can share this endpoint publicly using a sharing platform like [Ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).

If you're using **Datastax Langflow**, you can share the URL with any users within your **Organization**.

## Embed into site

The **Embed into site** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

For more information, see [Embedded chat widget](/embedded-chat-widget).
