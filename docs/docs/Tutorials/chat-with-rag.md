---
title: Create a vector RAG chatbot
slug: /chat-with-rag
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial demonstrates how you can use Langflow to create a chatbot application that uses Retrieval Augmented Generation (RAG) to embed your data as vectors in a vector database, and then chat with the data.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [A Langflow API key](/configuration-api-keys)
- [An OpenAI API key](https://platform.openai.com/)
- [Langflow JavaScript client installed](/typescript-client)
- Familiarity with vector search concepts and applications, such as [vector databases](https://www.datastax.com/guides/what-is-a-vector-database) and [RAG](https://www.datastax.com/guides/what-is-retrieval-augmented-generation)

## Create a vector RAG flow

1. In Langflow, click **New Flow**, and then select the **Vector Store RAG** template.

    <details>
      <summary>About the Vector Store RAG template</summary>

    This template has two flows.

    The **Load Data Flow** at the bottom of the workspace populates a vector store with data from a file.
    This data is used to respond to queries submitted to the **Retriever Flow**, which is at the top of the workspace.

    Specifically, the **Load Data Flow** ingests data from a local file, splits the data into chunks, loads and indexes the data in your vector database, and then computes embeddings for the chunks. The embeddings are also stored with the loaded data. This flow only needs to run when you need to load data into your vector database.

    The **Retriever Flow** receives chat input, generates an embedding for the input, and then uses several components to reconstruct chunks into text and generate a response by comparing the new embedding to the stored embeddings to find similar data.

    </details>

2. Add your **OpenAI** API key to both **OpenAI Embeddings** components.

3. Optional: Replace both **Astra DB** vector store components with a **Chrome DB** or another [vector store component](/components-vector-stores) of your choice.
This tutorial uses Chroma DB.

    The **Load Data Flow** should have **File**, **Split Text**, **Embedding Model**, vector store (such as **Chroma DB**), and **Chat Output** components:

    ![File loader chat flow](/img/tutorial-chatbot-embed-files.png)

    The **Retriever Flow** should have **Chat Input**, **Embedding Model**, vector store, **Parser**, **Prompt**, **Language Model**, and **Chat Output** components:

    ![Chat with RAG flow](/img/tutorial-chatbot-chat-flow.png)

    The flows are ready to use.
    Continue the tutorial to learn how to use the loading flow to load data into your vector store, and then call the chat flow in a chatbot application.

## Load data and generate embeddings

To load data and generate embeddings, you can use the Langflow UI or the `/v2/files` endpoint.

The Langflow UI option is simpler, but it is only recommended for scenarios where the user who created the flow is the same user who loads data into the database.

In situations where many users load data or you need to load data programmatically, use the Langflow API option.

<Tabs>
  <TabItem value="UI" label="UI" default>

    1. In your RAG chatbot flow, click the **File component**, and then click **File**.
    2. Select the local file you want to upload, and then click **Open**.
        The file is loaded to your Langflow server.
    3. To load the data into your vector store, click the vector store component, and then click <Icon name="Play" aria-hidden="true" /> **Run component** to run the selected component and all prior dependent components.

  </TabItem>
  <TabItem value="API" label="API">

    To load data programmatically, use the `/v2/files/` and `/v1/run/$FLOW_ID` endpoints. The first endpoint loads a file to your Langflow server, and then returns an uploaded file path. The second endpoint runs the **Load Data Flow**, referencing the uploaded file path, to chunk, embed, and load the data into the vector store.

    The following script demonstrates this process.
    For help with creating this script, use the [Langflow File Upload Utility](https://langflow-file-upload-examples.onrender.com/).

    ```js
    // Node 18+ example using global fetch, FormData, and Blob
    import fs from 'fs/promises';

    // 1. Prepare the form data with the file to upload
    const fileBuffer = await fs.readFile('FILE_NAME');
    const data = new FormData();
    data.append('file', new Blob([fileBuffer]), 'FILE_NAME');
    const headers = { 'x-api-key': 'LANGFLOW_API_KEY' };

    // 2. Upload the file to Langflow
    const uploadRes = await fetch('LANGFLOW_SERVER_ADDRESS/api/v2/files/', {
      method: 'POST',
      headers,
      body: data
    });
    const uploadData = await uploadRes.json();
    const uploadedPath = uploadData.path;

    // 3. Call the Langflow run endpoint with the uploaded file path
    const payload = {
      input_value: "Analyze this file",
      output_type: "chat",
      input_type: "text",
      tweaks: {
        'FILE_COMPONENT_NAME': {
          path: uploadedPath
        }
      }
    };
    const runRes = await fetch('LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': 'LANGFLOW_API_KEY' },
      body: JSON.stringify(payload)
    });
    const langflowData = await runRes.json();
    // Output only the message
    console.log(langflowData.outputs?.[0]?.outputs?.[0]?.results?.message?.data?.text);
    ```

  </TabItem>
</Tabs>

When the flow runs, the flow ingests the selected file, chunks the data, loads the data into the vector store database, and then generates embeddings for the chunks, which are also stored in the vector store.

Your database now contains data with vector embeddings that an LLM can use as context to respond to queries, as demonstrated in the next section of the tutorial.

## Chat with your flow from a JavaScript application

To chat with the data in your vector database, create a chatbot application that runs the **Retriever Flow** programmatically.

This tutorial uses JavaScript for demonstration purposes.

1. To construct the chatbot, gather the following information:

    * `LANGFLOW_SERVER_ADDRESS`: Your Langflow server's domain. The default value is `127.0.0.1:7860`. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `FLOW_ID`: Your flow's UUID or custom endpoint name. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `LANGFLOW_API_KEY`: A valid Langflow API key. To create an API key, see [API keys](/configuration-api-keys).

2. Copy the following script into a JavaScript file, and then replace the placeholders with the information you gathered in the previous step:

    ```js
    const readline = require('readline');
    const { LangflowClient } = require('@datastax/langflow-client');

    const API_KEY = 'LANGFLOW_API_KEY';
    const SERVER = 'LANGFLOW_SERVER_ADDRESS';
    const FLOW_ID = 'FLOW_ID';

    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

    // Initialize the Langflow client
    const client = new LangflowClient({
        baseUrl: SERVER,
        apiKey: API_KEY
    });

    async function sendMessage(message) {
        try {
            const response = await client.flow(FLOW_ID).run(message, {
                session_id: 'user_1'
            });

            // Use the convenience method to get the chat output text
            return response.chatOutputText() || 'No response';
        } catch (error) {
            return `Error: ${error.message}`;
        }
    }

    function chat() {
        console.log('🤖 Langflow RAG Chatbot (type "quit" to exit)\n');

        const ask = () => {
            rl.question('👤 You: ', async (input) => {
                if (['quit', 'exit', 'bye'].includes(input.trim().toLowerCase())) {
                    console.log('👋 Goodbye!');
                    rl.close();
                    return;
                }

                const response = await sendMessage(input.trim());
                console.log(`🤖 Assistant: ${response}\n`);
                ask();
            });
        };

        ask();
    }

    chat();
    ```

    The script creates a Node application that chats with the content in your vector database, using the `chat` input and output types to communicate with your flow.
    Chat maintains ongoing conversation context across multiple messages. If you used `text` type inputs and outputs, each request is a standalone text string.

    :::tip
    The [Langflow TypeScript client](/typescript-client) has a `chatOutputText()` convenience method that simplifies working with Langflow's complex JSON response structure.
    Instead of manually navigating through multiple levels of nested objects with `data.outputs[0].outputs[0].results.message.data.text`, the client automatically extracts the message text and handles potentially undefined values gracefully.
    :::

3. Save and run the script to send the requests and test the flow.

    <details>
    <summary>Response</summary>

    The following is an example of a response returned from this tutorial's flow. Due to the nature of LLMs and variations in your inputs, your response might be different.

    ```
    👤 You: Do you have any documents about engines?
    🤖 Assistant: Yes, the provided text contains several warnings and guidelines related to engine installation, maintenance, and selection. It emphasizes the importance of using the correct engine for specific applications, ensuring all components are in good condition, and following safety precautions to prevent fire or explosion. If you need more specific information or details, please let me know!

    👤 You: It should be about a Briggs and Stratton engine.
    🤖 Assistant: The text provides important safety and installation guidelines for Briggs & Stratton engines. It emphasizes that these engines should not be used on 3-wheel All-Terrain Vehicles (ATVs), motor bikes, aircraft products, or vehicles intended for competitive events, as such uses are not approved by Briggs & Stratton.

    If you have any specific questions about Briggs & Stratton engines or need further information, feel free to ask!
    ```

    </details>


## Next steps

For more information on building or extending this tutorial, see the following:

* [Model Context Protocol (MCP) servers](/mcp-server)
* [Langflow deployment overview](/deployment-overview)