---
title: Create a chatbot with your own files
slug: /chat-with-rag
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Create a chatbot application that uses Retrieval Augmented Generation.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/api-keys)

## Create a RAG flow

1. In Langflow, click **New Flow**, and then select the **Vector Store RAG** template.
2. Add your **OpenAI** API key to the **OpenAI Embeddings** component.
3. To confirm that the chatbot responds as expected, open the <Icon name="Play" aria-hidden="true" /> **Playground** and then ask a question.
The LLM should respond as the **Prompt** component specifies.
With the basic flow responding correctly, modify the **Prompt** component to accept additional inputs.


5. Add a [File component](/components-data#file) to the flow, and connect the **Raw Content** output to the Prompt component's `file` input.

    Your loading flow should look like this:

    ![File loader chat flow](/img/tutorial-embed-files.png)

    Your chat flow should look like this:

    ![Chat with RAG flow](/img/tutorial-chat-rag-flow.png)

    The flow is complete.
    If you'd like, add files to the File component and chat with it within the Langflow IDE.
    In the next section, you will load files and chat with your flow from a Python application.


## Load and embed a file

You have two options for loading and embedding a file into your vector database: the UI, or the `/v2/files` endpoint.

The UI is the easiest method.

<Tabs>
  <TabItem value="UI" label="UI" default>

1. In the **File component**, click **File**.
2. Select the local file you want to upload, and then click **Open**.
    The file is loaded to your Langflow server.
3. To run the embedding flow, in the vector store component, click <Icon name="Play" aria-hidden="true" /> **Run component**.
    The file is split by chunk overlap and chunk size, then embedded by the Embeddings component.

  </TabItem>
  <TabItem value="API" label="API">



  </TabItem>
</Tabs>



## Send requests to your flow from a JavaScript application

## Chat with your embedded documents


## Next steps

* [Model Context Protocol (MCP) servers](/mcp-server)
* [Langflow deployment overview](/deployment-overview)