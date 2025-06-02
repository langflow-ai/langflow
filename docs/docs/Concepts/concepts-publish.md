---
title: Publish flows
slug: /concepts-publish
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import ChatWidget from '@site/src/components/ChatWidget';

Langflow provides several ways to publish and integrate your flows into external applications. Whether you want to expose your flow as an API endpoint, embed it as a chat widget in your website, or share it as a public playground, this guide covers the options available for making your flows accessible to users.

## API access

To access the **API access** pane, click **Share**, and then click **API access**.

![](/img/api-pane.png)

<Tabs>

The **API access** pane presents code templates for integrating your flow into external applications.

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

### Input schema

The **Input schema** pane displays the available input parameters for your flow, and allows modifications to the listed parameters.

The **Endpoint name** field changes the endpoint name for your flow from the default UUID to the name you specify here.

The components and their parameters listed in the pane are available to be modified. Modifying the parameters changes the code parameters across all of the code examples.

For example, to change the model that the **Embeddings Provider** component is using:

1. Select **Enable Input**.
2. Select **Model Name**.
3. Select **gpt-4.1-mini**.

In the **API access** pane, inspect the code snippets.
The `model_name` parameter for the **OpenAI** model is changed for all requests to your flow.

```
"OpenAIModel-G3haJ":
{
"model_name":
"gpt-4.1-mini"
}
```

## Export

**Export** a flow to download it as a JSON file to your local machine.

1. To **Export** your flow, in the **Playground**, click **Share**, and then click **Export**.
2. To save your API keys with the flow, select **Save with my API keys**.
You can then **Import** the downloaded flow into another Langflow instance.

## MCP server

**MCP server** exposes your flows as [tools](https://modelcontextprotocol.io/docs/concepts/tools) that [MCP clients](https://modelcontextprotocol.io/clients) can use use to take actions.

For more information, see [MCP server](/mcp-server).

For information about using Langflow as an *MCP client*, see the [MCP connection component](/components-tools#mcp-connection).

## Embed into site

The **Embed into site** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

For more information, see [Embedded chat widget](/embedded-chat-widget).

## Shareable playground

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/{flow-id}` endpoint.

You can share this endpoint publicly using a sharing platform like [Ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).

If you're using **Datastax Langflow**, you can share the URL with any users within your **Organization**.