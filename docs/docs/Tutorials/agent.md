---
title: Connect applications to agents
slug: /agent-tutorial
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
- [Langflow JavaScript client installed](/typescript-client)

This tutorial uses an OpenAI LLM. If you want to use a different provider, you need a valid credential for that provider.

## Create an agentic flow

The following steps modify the [**Simple agent**](/simple-agent) template to connect [**Directory**](/components-data#directory) and [**Web search**](/components-data#web-search) components as tools for the agent.
The Directory component loads all files of a given type from a target directory on your local machine, and the Web search component performs a DuckDuckGo search.

1. In Langflow, click **New Flow**, and then select the **Simple agent** template.
2. Remove the **URL** and **Calculator** tools, and drag the [**Directory**](/components-data#directory) and [**Web search**](/components-data#web-search) components to your workspace.
3. In the **Directory** component's **Path** field, enter the path to your directory, and the types of files you want to provide to your agent.
In this example, the directory name is `customer_orders` and the file type is `.csv`, because you want the agent to have access to a record of customer purchases.
If you don't have a csv on hand, you can download [customer-orders.csv](/files/customer_orders/customer_orders.csv) and save it in a folder called `customer_orders`.
4. In the **Directory** and **Web search** components, enable **Tool Mode**, and connect the **Toolset** port to the agent's **Tools** port.
This mode registers the connected tools with your Agent, so it understands what they do and how to use them.
5. In the **Agent** component, enter your OpenAI API key.

    If you want to use a different provider or model, edit the **Model Provider**, **Model Name**, and **API Key** fields accordingly.

6. To verify that your flow is operational, click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM a question, such as `Recommend 3 used items for carol.davis@example.com, based on previous orders.`
The LLM should respond with recommendations and web links for items based on previous orders in `customer_orders.csv`.
The Playground displays the agent's chain of thought as it uses the Directory component's `as_dataframe` tool to retrieve a [DataFrame](/concepts-objects#dataframe-object), and the Web search component's `perform_search` tool to find links to related items.

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
        import { LangflowClient } from "@datastax/langflow-client";

        const LANGFLOW_SERVER_ADDRESS = 'LANGFLOW_SERVER_ADDRESS';
        const FLOW_ID = 'FLOW_ID';
        const LANGFLOW_API_KEY = 'LANGFLOW_API_KEY';
        const email = "isabella.rodriguez@example.com";

        async function runAgentFlow(): Promise<void> {
            try {
                // Initialize the Langflow client
                const client = new LangflowClient({
                    baseUrl: LANGFLOW_SERVER_ADDRESS,
                    apiKey: LANGFLOW_API_KEY
                });

                console.log(`Connecting to Langflow server at: ${LANGFLOW_SERVER_ADDRESS} `);
                console.log(`Flow ID: ${FLOW_ID}`);
                console.log(`Email: ${email}`);

                // Get the flow instance
                const flow = client.flow(FLOW_ID);

                // Run the flow with the email as input
                console.log('\nSending request to agent...');
                const response = await flow.run(email, {
                    session_id: email // Use email as session ID for context
                });

                console.log('\n=== Response from Langflow ===');
                console.log('Session ID:', response.sessionId);

                // Extract URLs from the chat message
                const chatMessage = response.chatOutputText();
                console.log('\n=== URLs from Chat Message ===');
                const messageUrls = chatMessage.match(/https?:\/\/[^\s"')\]]+/g) || [];
                const cleanMessageUrls = [...new Set(messageUrls)].map(url => url.trim());
                console.log('URLs from message:');
                cleanMessageUrls.slice(0, 3).forEach(url => console.log(url));

            } catch (error) {
                console.error('Error running flow:', error);

                // Provide error messages
                if (error instanceof Error) {
                    if (error.message.includes('fetch')) {
                        console.error('\nMake sure your Langflow server is running and accessible at:', LANGFLOW_SERVER_ADDRESS);
                    }
                    if (error.message.includes('401') || error.message.includes('403')) {
                        console.error('\nCheck your API key configuration');
                    }
                    if (error.message.includes('404')) {
                        console.error('\nCheck your Flow ID - make sure it exists and is correct');
                    }
                }
            }
        }

        // Run the function
        console.log('Starting Langflow Agent...\n');
        runAgentFlow().catch(console.error);
        ```
    </details>

3. Save and run the script to send the request and test the flow.

    <details closed>
    <summary>Response</summary>

    The following is an example of a response returned from this tutorial's flow. Due to the nature of LLMs and variations in your inputs, your response might be different.

    ```
    Starting Langflow Agent...

    Connecting to Langflow server at: http://localhost:7860
    Flow ID: local-db-search
    Email: isabella.rodriguez@example.com

    Sending request to agent...

    === Response from Langflow ===
    Session ID: isabella.rodriguez@example.com

    URLs found:
    https://www.facebook.com/marketplace/258164108225783/electronics/
    https://www.facebook.com/marketplace/458332108944152/furniture/
    https://www.facebook.com/marketplace/613732137493719/kitchen-cabinets/
    ```

    </details>

4. Check your flow's **Playground**.
    New sessions appear named after the user's email address.
    Keeping sessions distinct helps the agent maintain context. For more on session IDs, see [Session ID](/session-id).

Your application receives three URLs for recommended used items based on a customer's previous orders in your local CSV, all without changing any code.

## Next steps

You can build out this tutorial by connecting more tools to the agent, or add even more context for your LLMs by connecting [MCP servers](/mcp-client) to your agent as tools.