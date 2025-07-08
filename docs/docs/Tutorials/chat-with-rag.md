---
title: Create a vector RAG chatbot
slug: /chat-with-rag
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Create a chatbot application that uses Retrieval Augmented Generation to embed your data as vectors in a vector database, and then chat with the embedded data.
This example uses the [**Chroma DB**](/components-vector-stores#chroma-db) vector store, but you can use any supported [Vector store component](/components-vector-stores).

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create a vector RAG flow

1. In Langflow, click **New Flow**, and then select the **Vector Store RAG** template.
2. Add your **OpenAI** API key to the **OpenAI Embeddings** components.
3. Replace both **Astra DB** vector store components with [**Chroma DB**](/components-vector-stores#chroma-db) vector store components, or another vector store of your choice.

    Your loading flow should look like this:

    ![File loader chat flow](/img/tutorial-chatbot-embed-files.png)

    Your chat flow should look like this:

    ![Chat with RAG flow](/img/tutorial-chatbot-chat-flow.png)

    The flow is complete.
    In the next section, you will embed files into your database, and then create a chatbot to chat with them.

## Load and embed a file

You have two options for loading and embedding a file into your vector database: the UI, or the `/v2/files` endpoint.

The UI is the easiest method.

<Tabs>
  <TabItem value="UI" label="UI" default>

    1. In the **File component**, click **File**.
    2. Select the local file you want to upload, and then click **Open**.
        The file is loaded to your Langflow server.
    3. To run the embedding flow, in the vector store component, click <Icon name="Play" aria-hidden="true" /> **Run component**.
        The file is split by chunk overlap and chunk size, and then the chunked files are embedded by the Embeddings component into the vector database.

  </TabItem>
  <TabItem value="API" label="API">

    To upload files with the API, send a request to the flow's **File** component containing the uploaded path to your file.
    The fastest way to form this request is with the [Langflow File Upload Utility](https://langflow-file-upload-examples.onrender.com/). For example:

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

## Chat with your flow from a JavaScript application

With your files loaded and embedded in your vector database, create a JavaScript chatbot to chat with your data.

1. To construct the chatbot, gather the following information:

    Replace the following values:
    * `LANGFLOW_SERVER_ADDRESS`: Your Langflow server's domain. The default value is `127.0.0.1:7860`. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-pane).
    * `FLOW_ID`: Your flow's UUID or custom endpoint name. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-pane).
    * `LANGFLOW_API_KEY`: A valid Langflow API key. To create an API key, see [API keys](/configuration-api-keys).

2. Copy the following script into a JavaScript file, and then replace the placeholders with the information you gathered in the previous step:

    ```js
    #!/usr/bin/env node

    const readline = require('readline');
    const fetch = require('node-fetch');

    const API_KEY = 'LANGFLOW_API_KEY';
    const SERVER = 'LANGFLOW_SERVER_ADDRESS';
    const FLOW_ID = 'FLOW_ID';

    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

    async function sendMessage(message) {
        try {
            const response = await fetch(`${SERVER}/api/v1/run/${FLOW_ID}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
                body: JSON.stringify({
                    output_type: 'chat',
                    input_type: 'chat',
                    input_value: message,
                    session_id: 'user_1'
                })
            });

            const data = await response.json();
            return data.outputs?.[0]?.outputs?.[0]?.results?.message?.data?.text || 'No response';
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

    The script creates a Node application that chats with the content in your vector database.

    The script uses the `chat` input and output types to communicate with your Langflow flow.
    Chat maintains ongoing conversation context across multiple messages. If you used `text` type inputs and outputs, each request is a standalone text string.

    The script parses the message text out of Langflow's JSON response and presents it back to your application, where you can chat with it more with follow-up questions.
    ```json
    {
      "outputs": [{
        "outputs": [{
          "results": {
            "message": {
              "data": {
                "text": "The actual response text"
              }
            }
          }
        }]
      }]
    }
    ```

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

* [Model Context Protocol (MCP) servers](/mcp-server)
* [Langflow deployment overview](/deployment-overview)