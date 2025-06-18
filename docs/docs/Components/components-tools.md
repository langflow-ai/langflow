---
title: Tools
slug: /components-tools
---

import Icon from "@site/src/components/icon";

# Tool components in Langflow

Tools are typically connected to agent components at the **Tools** port. Agents use LLMs as a reasoning engine to decide which of the connected tool components to use to solve a problem.

Tools in agentic functions are, essentially, functions that the agent can call to perform tasks or access external resources.
A function is wrapped as a `Tool` object, with a common interface the agent understands.
Agents become aware of tools through tool registration, where the agent is provided a list of available tools, typically at agent initialization. The `Tool` object's description tells the agent what the tool can do.

The agent then uses a connected LLM to reason through the problem to decide which tool is best for the job.

## Use a tool in a flow

Tools are typically connected to agent components at the **Tools** port.

The [simple agent starter project](/starter-projects-simple-agent) uses URL and Calculator tools connected to an [agent component](/components-agents#agent-component) to answer a user's questions. The OpenAI LLM acts as a brain for the agent to decide which tool to use.

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

To make a component into a tool that an agent can use, enable **Tool mode** in the component. Enabling **Tool mode** modifies a component input to accept calls from an agent.
If the component you want to connect to an agent doesn't have a **Tool mode** option, you can modify the component's inputs to become a tool.
For an example, see [Make any component a tool](/agents-tools#make-any-component-a-tool).

## arXiv

This component searches and retrieves papers from [arXiv.org](https://arXiv.org).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| search_query | String | The search query for arXiv papers. For example, `quantum computing`. |
| search_type | String | The field to search in. |
| max_results | Integer | The maximum number of results to return. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| papers | List[Data] | A list of retrieved arXiv papers. |

</details>

## Astra DB tool

This component allows agents to query data from Astra DB collections.

To use this tool in a flow, connect it to an **Agent** component.
The flow looks like this:

![Astra DB JSON tool connected to an Agent](/img/component-astra-db-json-tool.png)

The **Tool Name** and **Tool Description** fields are required for the Agent to decide when to use the tool.
**Tool Name** cannot contain spaces.

The values for **Collection Name**, **Astra DB Application Token**, and **Astra DB API Endpoint** are found in your Astra DB deployment. For more information, see the [DataStax documentation](https://docs.datastax.com/en/astra-db-serverless/databases/create-database.html).

In this example, an **OpenAI** embeddings component is connected to use the Astra DB tool component's **Semantic Search** capability.
To use **Semantic Search**, you must have an embedding model or Astra DB Vectorize enabled.
If you try to run the flow without an embedding model, you will get an error.

Open the **Playground** and ask a question about your data.
The Agent uses the **Astra DB Tool** to return information about your collection.

### Define Astra DB tool parameters

The **Tool Parameters** configuration pane allows you to define parameters for [filter conditions](https://docs.datastax.com/en/astra-db-serverless/api-reference/document-methods/find-many.html#parameters) for the component's **Find** command.

These filters become available as parameters that the LLM can use when calling the tool, with a better understanding of each parameter provided by the **Description** field.

1. To define a parameter for your query, in the **Tool Parameters** pane, click <Icon name="Plus" aria-label="Add"/>.
2. Complete the fields based on your data. For example, with this filter, the LLM can filter by unique `customer_id` values.

* Name: `customer_id`
* Attribute Name: Leave empty if the attribute matches the field name in the database.
* Description: `"The unique identifier of the customer to filter by"`.
* Is Metadata: `False` unless the value stored in the metadata field.
* Is Mandatory: `True` to require this filter.
* Is Timestamp: `False` since the value is an ID, not a timestamp.
* Operator: `$eq` to look for an exact match.

If you want to apply filters regardless of the LLM's input, use the **Static Filters** option, which is available in the component's **Controls** pane.

| Parameter | Description |
|-----------|-------------|
| Name | The name of the parameter that is exposed to the LLM. It can be the same as the underlying field name or a more descriptive label. The LLM uses this name, along with the description, to infer what value to provide during execution. |
| Attribute Name | When the parameter name shown to the LLM differs from the actual field or property in the database, use this setting to map the user-facing name to the correct attribute. For example, to apply a range filter to the timestamp field, define two separate parameters, such as `start_date` and `end_date`, that both reference the same timestamp attribute. |
| Description | Provides instructions to the LLM on how the parameter should be used. Clear and specific guidance helps the LLM provide valid input. For example, if a field such as `specialty` is stored in lowercase, the description should indicate that the input must be lowercase. |
| Is Metadata | When loading data using LangChain or Langflow, additional attributes may be stored under a metadata object. If the target attribute is stored this way, enable this option. It adjusts the query by generating a filter in the format: `{"metadata.<attribute_name>": "<value>"}` |
| Is Timestamp | For date or time-based filters, enable this option to automatically convert values to the timestamp format that the Astrapy client expects. This ensures compatibility with the underlying API without requiring manual formatting. |
| Operator | Defines the filtering logic applied to the attribute. You can use any valid [Data API filter operator](https://docs.datastax.com/en/astra-db-serverless/api-reference/filter-operator-collections.html). For example, to filter a time range on the timestamp attribute, use two parameters: one with the `$gt` operator for "greater than", and another with the `$lt` operator for "less than". |

<details>
<summary>Parameters</summary>

**Inputs**

| Name              | Type   | Description                                                                                                                      |
|-------------------|--------|----------------------------------------------------------------------------------------------------------------------------------|
| Tool Name         | String | The name used to reference the tool in the agent's prompt.                                                                       |
| Tool Description  | String | A brief description of the tool. This helps the model decide when to use it.                                                     |
| Collection Name   | String | The name of the Astra DB collection to query.                                                                                    |
| Token             | SecretString | The authentication token for accessing Astra DB.                                                                                 |
| API Endpoint      | String | The Astra DB API endpoint.                                                                                                       |
| Projection Fields | String | The attributes to return, separated by commas. The default is `*`.                                                                     |
| Tool Parameters   | Dict   | Parameters the model needs to fill to execute the tool. For required parameters, use an exclamation mark, for example `!customer_id`. |
| Static Filters    | Dict   | Attribute-value pairs used to filter query results.                                                                              |
| Limit             | String | The number of documents to return.                                                                                               |


**Outputs**

The **Data** output is used when directly querying Astra DB, while the **Tool** output is used when integrating with agents.

| Name | Type | Description |
|------|------|-------------|
| Data | List[Data] | A list of [Data](/concepts-objects) objects containing the query results from Astra DB. Each `Data` object contains the document fields specified by the projection attributes. Limited by the `number_of_results` parameter. |
| Tool | StructuredTool | A LangChain `StructuredTool` object that can be used in agent workflows. Contains the tool name, description, argument schema based on tool parameters, and the query function. |

</details>

## Astra DB CQL Tool

The `Astra DB CQL Tool` allows agents to query data from CQL tables in Astra DB.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| Tool Name | String | The name used to reference the tool in the agent's prompt. |
| Tool Description | String | A brief description of the tool to guide the model in using it. |
| Keyspace | String | The name of the keyspace. |
| Table Name | String | The name of the Astra DB CQL table to query. |
| Token | SecretString | The authentication token for Astra DB. |
| API Endpoint | String | The Astra DB API endpoint. |
| Projection Fields | String | The attributes to return, separated by commas. Default: "*". |
| Partition Keys | Dict | Required parameters that the model must fill to query the tool. |
| Clustering Keys | Dict | Optional parameters the model can fill to refine the query. Required parameters should be marked with an exclamation mark, for example, `!customer_id`. |
| Static Filters | Dict | Attribute-value pairs used to filter query results. |
| Limit | String | The number of records to return. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| Data | List[Data] | A list of [Data](/concepts-objects) objects containing the query results from the Astra DB CQL table. Each Data object contains the document fields specified by the projection fields. Limited by the `number_of_results` parameter. |
| Tool | StructuredTool | A LangChain StructuredTool object that can be used in agent workflows. Contains the tool name, description, argument schema based on partition and clustering keys, and the query function. |

</details>

## Bing Search API

This component allows you to call the Bing Search API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| bing_subscription_key | SecretString | A Bing API subscription key. |
| input_value | String | The search query input. |
| bing_search_url | String | A custom Bing Search URL. |
| k | Integer | The number of search results to return. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| results | List[Data] | A list of search results. |
| tool | Tool | A Bing Search tool for use in LangChain. |

</details>

## Combinatorial Reasoner

This component runs Icosa's Combinatorial Reasoning (CR) pipeline on an input to create an optimized prompt with embedded reasons. For more information, see [Icosa computing](https://www.icosacomputing.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| prompt | String | The input to run CR on. |
| openai_api_key | SecretString | An OpenAI API key for authentication. |
| username | String | A username for Icosa API authentication. |
| password | SecretString | A password for Icosa API authentication. |
| model_name | String | The OpenAI LLM to use for reason generation. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| optimized_prompt | Message | A message object containing the optimized prompt. |
| reasons | List[String] | A list of the selected reasons that are embedded in the optimized prompt. |

</details>

## DuckDuckGo search

This component performs web searches using the [DuckDuckGo](https://www.duckduckgo.com) search engine with result-limiting capabilities.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| input_value | String | The search query to execute with DuckDuckGo. |
| max_results | Integer | The maximum number of search results to return. Default: 5. |
| max_snippet_length | Integer | The maximum length of each result snippet. Default: 100. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| data | List[Data] | A list of search results as Data objects containing snippets and full content. |
| text | String | The search results formatted as a single text string. |

</details>

## Exa Search

This component provides an [Exa Search](https://exa.ai/) toolkit for search and content retrieval.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| metaphor_api_key | SecretString | An API key for Exa Search. |
| use_autoprompt | Boolean | Whether to use the autoprompt feature. Default: true. |
| search_num_results | Integer | The number of results to return for search. Default: 5. |
| similar_num_results | Integer | The number of similar results to return. Default: 5. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| tools | List[Tool] | A list of search tools provided by the toolkit. |

</details>

## Glean Search API

This component allows you to call the Glean Search API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| glean_api_url | String | The URL of the Glean API. |
| glean_access_token | SecretString | An access token for Glean API authentication. |
| query | String | The search query input. |
| page_size | Integer | The number of results per page. Default: 10. |
| request_options | Dict | Additional options for the API request. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| results | List[Data] | A list of search results. |
| tool | Tool | A Glean Search tool for use in LangChain. |

</details>

## Google Serper API

This component allows you to call the Serper.dev Google Search API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| serper_api_key | SecretString | An API key for Serper.dev authentication. |
| input_value | String | The search query input. |
| k | Integer | The number of search results to return. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| results | List[Data] | A list of search results. |
| tool | Tool | A Google Serper search tool for use in LangChain. |

</details>

## MCP connection

The **MCP connection** component connects to a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server and exposes the MCP server's tools as tools for Langflow agents.

In addition to being an MCP client that can leverage MCP servers, the **MCP connection** component's [SSE mode](#mcp-sse-mode) allows you to connect your flow to the Langflow MCP server at the `/api/v1/mcp/sse` API endpoint, exposing all flows within your [project](/concepts-overview#projects) as tools within a flow.

To use the **MCP connection** component with an agent component, follow these steps:

1. Add the **MCP connection** component to your workflow.

2. In the **MCP connection** component, in the **MCP Command** field, enter the command to start your MCP server. For example, to start a [Fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) server, the command is:

    ```bash
    uvx mcp-server-fetch
    ```

    `uvx` is included with `uv` in the Langflow package.
    To use `npx` server commands, you must first install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).
    For an example of starting `npx` MCP servers, see [Connect an Astra DB MCP server to Langflow](/mcp-component-astra).

    To include environment variables with your server command, add them to the **Env** field like this:

    ```bash
    ASTRA_DB_APPLICATION_TOKEN=AstraCS:...
    ```

    :::important
    Langflow passes environment variables from the `.env` file to MCP, but not global variables declared in the UI.
    To add a value for an environment variable as a global variable, add it to Langflow's `.env` file at startup.
    For more information, see [global variables](/configuration-global-variables).
    :::

3. Click <Icon name="RefreshCw" aria-label="Refresh"/> to get the server's list of **Tools**.

4. In the **Tool** field, select the server tool you want the component to use.
The available fields change based on the selected tool.
For information on the parameters, see the MCP server's documentation.

5. In the **MCP connection** component, enable **Tool mode**.
Connect the **MCP connection** component's **Toolset** port to an **Agent** component's **Tools** port.

    The flow looks similar to this:
    ![MCP connection component](/img/component-mcp-stdio.png)

6. Open the **Playground**.
Ask the agent to summarize recent tech news. The agent calls the MCP server function `fetch` and returns the summary.
This confirms the MCP server is connected, and its tools are being used in Langflow.

For more information, see [MCP server](/mcp-server).

### MCP Server-Sent Events (SSE) mode {#mcp-sse-mode}

:::important
If you're using **Langflow for Desktop**, the default address is `http://localhost:7868/`.
:::

The MCP component's SSE mode connects your flow to the Langflow MCP server through the component.
This allows you to use all flows within your [project](/concepts-overview#projects) as tools within a flow.

1. In the **MCP connection** component, select **SSE**.
A default address appears in the **MCP SSE URL** field.
2. In the **MCP SSE URL** field, modify the default address to point at the SSE endpoint of the Langflow server you're currently running.
The default value is `http://localhost:7860/api/v1/mcp/sse`.
3. In the **MCP connection** component, click <Icon name="RefreshCw" aria-label="Refresh"/> to retrieve the server's list of **Tools**.
4. Click the **Tools** field.
All of your flows are listed as tools.
5. Enable **Tool Mode**, and then connect the **MCP connection** component to an agent component's tool port.
The flow looks like this:
![MCP component with SSE mode enabled](/img/component-mcp-sse-mode.png)
6. Open the **Playground** and chat with your tool.
The agent chooses the correct tool based on your query.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| command | String | The MCP command. Default: `uvx mcp-sse-shim@latest`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| tools | List[Tool] | A list of tools exposed by the MCP server. |

</details>

## Wikidata

This component performs a search using the Wikidata API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| query | String | The text query for similarity search on Wikidata. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| data | List[Data] | The search results from Wikidata API as a list of Data objects. |
| text | Message | The search results formatted as a text message. |

</details>

## Legacy components

Legacy components are available for use but are no longer supported.

### Calculator Tool

This component allows you to evaluate basic arithmetic expressions. It supports addition, subtraction, multiplication, division, and exponentiation.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| expression | String | The arithmetic expression to evaluate. For example, `4*4*(33/22)+12-20`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| result | Tool | A calculator tool for use in LangChain. |

</details>

### Google Search API

This component allows you to call the Google Search API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| google_api_key | SecretString | A Google API key for authentication. |
| google_cse_id | SecretString | A Google Custom Search Engine ID. |
| input_value | String | The search query input. |
| k | Integer | The number of search results to return. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| results | List[Data] | A list of search results. |
| tool | Tool | A Google Search tool for use in LangChain. |

</details>

### Python Code Structured Tool

This component creates a structured tool from Python code using a dataclass.

The component dynamically updates its configuration based on the provided Python code, allowing for custom function arguments and descriptions.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| tool_code | String | The Python code for the tool's dataclass. |
| tool_name | String | The name of the tool. |
| tool_description | String | The description of the tool. |
| return_direct | Boolean | Whether to return the function output directly. |
| tool_function | String | The selected function for the tool. |
| global_variables | Dict | Global variables or data for the tool. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| result_tool | Tool | A structured tool created from the Python code. |

</details>

### Python REPL Tool

This component creates a Python REPL (Read-Eval-Print Loop) tool for executing Python code.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| name | String | The name of the tool. Default: `python_repl`. |
| description | String | A description of the tool's functionality. |
| global_imports | List[String] | A list of modules to import globally. Default: `math`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| tool | Tool | A Python REPL tool for use in LangChain. |

</details>

### Retriever Tool

This component creates a tool for interacting with a retriever in LangChain.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| retriever | BaseRetriever | The retriever to interact with. |
| name | String | The name of the tool. |
| description | String | A description of the tool's functionality. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| tool | Tool | A retriever tool for use in LangChain. |

</details>

### Search API

This component calls the `searchapi.io` API. It can be used to search the web for information.

For more information, see the [SearchAPI documentation](https://www.searchapi.io/docs/google).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| engine | String | The search engine to use. Default: `google`. |
| api_key | SecretString | The API key for authenticating with SearchAPI. |
| input_value | String | The search query or input for the API call. |
| search_params | Dict | Additional parameters for customizing the search. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| data | List[Data] | A list of Data objects containing search results. |
| tool | Tool | A Tool object for use in LangChain workflows. |

</details>

### SearXNG Search Tool

This component creates a tool for searching using SearXNG, a metasearch engine.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| url | String | The URL of the SearXNG instance. |
| max_results | Integer | The maximum number of results to return. |
| categories | List[String] | The categories to search in. |
| language | String | The language for the search results. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| result_tool | Tool | A SearXNG search tool for use in LangChain. |

</details>

### Wikipedia API

This component creates a tool for searching and retrieving information from Wikipedia.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| input_value | String | The search query input. |
| lang | String | The language code for Wikipedia. Default: `en`. |
| k | Integer | The number of results to return. |
| load_all_available_meta | Boolean | Whether to load all available metadata. |
| doc_content_chars_max | Integer | The maximum number of characters for document content. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| results | List[Data] | A list of Wikipedia search results. |
| tool | Tool | A Wikipedia search tool for use in LangChain. |

</details>

## Deprecated components

Deprecated components have been replaced by newer alternatives and should not be used in new projects.

### MCP Tools (stdio)
:::important
This component is deprecated as of Langflow version 1.3.
Instead, use the [MCP connection component](/components-tools#mcp-connection)
:::


### MCP Tools (SSE)
:::important
This component is deprecated as of Langflow version 1.3.
Instead, use the [MCP connection component](/components-tools#mcp-connection)
:::

