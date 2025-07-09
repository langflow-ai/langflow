---
title: Connect an agent
slug: /chat-with-sqlite
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial shows you how to connect a JavaScript application to a Langflow [agent](/agents).

With the agent connected, your application can use any connected tools to retrieve more contextual and timely data without changing any application code. The tools are selected by the agent's internal LLM to solve problems and answer questions.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [A Langflow API key](/configuration-api-keys)
- [An OpenAI API key](https://platform.openai.com/api-keys)

This tutorial uses an OpenAI LLM. If you want to use a different provider, you need a valid credential for that provider.

## Create an agentic flow

The following steps modify the [**Simple agent**](/simple-agent) template to connect [**Directory**](/components-data#directory) and [**Web search**](/components-data#web-search) components as tools for the agent.
The Directory component loads all files of a given type from a target directory on your local machine, and the Web search component performs a DuckDuckGo search.

1. In Langflow, click **New Flow**, and then select the **Simple agent** template.
2. Remove the **URL** and **Calculator** tools, and drag the [**Directory**](/components-data#directory) and [**Web search**](/components-data#web-search) components to your workspace.
3. In the **Directory** component's **Path** field, enter the path to your directory, and the types of files you want to provide to your agent.
In this example, the directory name is `customer_orders` and the file type is `.csv`, because you want the agent to have access to a record of customer purchases.
If you don't have a csv on hand, you can download [customer-orders.csv](/files/customer-orders.csv) and save it in a folder called `customer_orders`.
4. In the **Directory** and **Web search** components, enable **Tool Mode**, and connect the **Toolset** port to the agent's **
This mode registers the connected tools with your Agent, so it understands what they do and how to use them.
5. In the **Agent** component, enter your OpenAI API key.

    If you want to use a different provider or model, edit the **Model Provider**, **Model Name**, and **API Key** fields accordingly.

6. To verify that your flow is operational, click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM a question, such as `Recommend 3 used items for carol.davis@example.com, based on previous orders.`
The LLM should respond with recommendations and web links for items based on previous orders in `customer_orders.csv`.
The Playground displays the agent's chain of thought as it uses the Directory component's `as_dataframe` tool to retrieve a [DataFrame](/concepts-objects#dataframe-objects), and the Web search component's `perform_search` tool to find links to related items.

## Send requests to your flow from a JavaScript application

With your flow operational, connect it to a JavaScript application to use the agent's responses.

In this example, the application sends a customer's email address to the Langflow agent. The agent compares the customer's previous orders within the Directory component, searches the web for used versions of those items, and returns three results.

1. To include the email address as a value in your flow, add a [Prompt](/components-prompts) component to your flow between the **Chat Input** and **Agent**.
2. In the Prompt component's **Template** field, enter `Recommend 3 used items for ${email}, based on previous orders.`

    The flow appears like this.

    ![An agent component connected to web search and directory components](/img/tutorial-agent-with-directory.png)

3. To construct a JavaScript application to connect to your flow, gather the following information:

    * `LANGFLOW_SERVER_ADDRESS`: Your Langflow server's domain. The default value is `127.0.0.1:7860`. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-pane).
    * `FLOW_ID`: Your flow's UUID or custom endpoint name. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-pane).
    * `LANGFLOW_API_KEY`: A valid Langflow API key. To create an API key, see [API keys](/configuration-api-keys).

2. Copy the following script into a JavaScript file, and then replace the placeholders with the information you gathered in the previous step.
If you're using the `customer_orders.csv` example file, you can run this as-is with the example email address.

    <details open>
    <summary>JavaScript</summary>

        ```js
        // Configuration - Replace these values with your own
        const LANGFLOW_SERVER_ADDRESS = 'LANGFLOW_SERVER_ADDRESS';
        const FLOW_ID = 'FLOW_ID';
        const LANGFLOW_API_KEY = 'LANGFLOW_API_KEY';
        const email = "alice.smith@example.com";

        // Request payload
        const payload = {
            "output_type": "chat",
            "input_type": "chat",
            "input_value": email,
            "session_id": email
        };

        // Make the API request
        fetch(`${LANGFLOW_SERVER_ADDRESS}/api/v1/run/${FLOW_ID}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                "x-api-key": LANGFLOW_API_KEY
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            // Just search for URLs in the entire response
            const responseText = JSON.stringify(data);
            const urls = responseText.match(/https?:\/\/[^\s"')\]]+/g) || [];

            // Clean the URLs and remove duplicates
            const cleanUrls = [...new Set(urls)].map(url => url.trim());
            console.log('URLs found:');
            cleanUrls.slice(0, 3).forEach(url => console.log(url));
        })
        .catch(err => console.error(err));
        ```
    </details>

3. Save and run the script to send the request and test the flow.

    <details closed>
    <summary>Response</summary>

    The following is an example of a response returned from this tutorial's flow. Due to the nature of LLMs and variations in your inputs, your response might be different.

    ```
    URLs found:
    https://www.facebook.com/marketplace/108225782538164/electronics/
    https://www.facebook.com/marketplace/108944152458332/furniture/
    https://www.facebook.com/marketplace/137493719613732/kitchen-cabinets/
    ```

    </details>

4. Check your flow's **Playground**.
New sessions appear named after the user's email address.
Keeping sessions distinct helps the agent maintain context. For more on session IDs, see [Session ID](/session-id).

    The preceding example stringifies the entire Langflow response and pattern-matches for the first three URLs.
    Alternatively, for more precision, navigate through the response structure to the `artifacts.message` field and match the first three markdown links there.

    <details closed>
    <summary>Alternate message extraction</summary>

    ```js
    .then(data => {
        // Navigate to the specific message field
        const message = data.outputs?.['0']?.outputs?.['0']?.artifacts?.message || '';

        // Extract URLs from markdown links in the message
        const urlMatches = message.match(/\[([^\]]+)\]\(([^)]+)\)/g) || [];
        const urls = urlMatches.map(match => {
            const urlMatch = match.match(/\[([^\]]+)\]\(([^)]+)\)/);
            return urlMatch ? urlMatch[2] : null;
        }).filter(url => url);

        // Print the first 3 URLs
        console.log('URLs found:');
        urls.slice(0, 3).forEach(url => console.log(url));
    })
    .catch(err => console.error(err));
    ```

    </details>

    Which ever approach you choose, your application receives three URLs for recommended used items based on a customer's previous orders in your local CSV, all without changing any code.

## Next steps

You can build out this tutorial by connecting more tools to the agent, or add even more context for your LLMs by connecting [MCP servers](/mcp-clients) to your agent as tools.