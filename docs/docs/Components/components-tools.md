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
For an example, see [Make any component a tool](/agents-tool-calling-agent-component#make-any-component-a-tool).

## arXiv

This component searches and retrieves papers from [arXiv.org](https://arXiv.org).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| search_query | Search Query | The search query for arXiv papers (for example, `quantum computing`) |
| search_type | Search Field | The field to search in |
| max_results | Max Results | Maximum number of results to return |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| papers | Papers | List of retrieved arXiv papers |

</details>

## Astra DB Tool

The `Astra DB Tool` allows agents to connect to and query data from Astra DB collections.

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
| Projection Fields | String | The attributes to return, separated by commas. Default: "*".                                                                     |
| Tool Parameters   | Dict   | Parameters the model needs to fill to execute the tool. For required parameters, use an exclamation mark (for example, `!customer_id`). |
| Static Filters    | Dict   | Attribute-value pairs used to filter query results.                                                                              |
| Limit             | String | The number of documents to return.                                                                                               |

**Outputs**

The Data output is primarily used when directly querying Astra DB, while the Tool output is used when integrating with LangChain agents or chains.

| Name | Type | Description |
|------|------|-------------|
| Data | List[`Data`] | A list of [Data](/concepts-objects) objects containing the query results from Astra DB. Each `Data` object contains the document fields specified by the projection attributes. Limited by the `number_of_results` parameter. |
| Tool | StructuredTool | A LangChain `StructuredTool` object that can be used in agent workflows. Contains the tool name, description, argument schema based on tool parameters, and the query function. |

</details>

## Astra DB CQL Tool

The `Astra DB CQL Tool` allows agents to query data from CQL tables in Astra DB.

The main difference between this tool and the **Astra DB Tool** is that this tool is specifically designed for CQL tables and requires partition keys for querying, while also supporting clustering keys for more specific queries.

<details>
<summary>Parameters</summary>

**Inputs**

| Name              | Type   | Description                                                                                                                                        |
|-------------------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| Tool Name         | String | The name used to reference the tool in the agent's prompt.                                                                                         |
| Tool Description  | String | A brief description of the tool to guide the model in using it.                                                                                    |
| Keyspace          | String | The name of the keyspace.                                                                                                                          |
| Table Name        | String | The name of the Astra DB CQL table to query.                                                                                                       |
| Token             | SecretString | The authentication token for Astra DB.                                                                                                             |
| API Endpoint      | String | The Astra DB API endpoint.                                                                                                                         |
| Projection Fields | String | The attributes to return, separated by commas. Default: "*".                                                                                       |
| Partition Keys    | Dict   | Required parameters that the model must fill to query the tool.                                                                                    |
| Clustering Keys   | Dict   | Optional parameters the model can fill to refine the query. Required parameters should be marked with an  exclamation mark (for example, `!customer_id`). |
| Static Filters    | Dict   | Attribute-value pairs used to filter query results.                                                                                                |
| Limit             | String | The number of records to return.                                                                                                                   |

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

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| bing_subscription_key   | SecretString | Bing API subscription key             |
| input_value            | String       | Search query input                    |
| bing_search_url        | String       | Custom Bing Search URL (optional)    |
| k                      | Integer      | Number of search results to return    |

**Outputs**

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Bing Search tool for use in LangChain|

</details>

## Combinatorial Reasoner

This component runs Icosa's Combinatorial Reasoning (CR) pipeline on an input to create an optimized prompt with embedded reasons. For more information, see [Icosa computing](https://www.icosacomputing.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                   | Display Name | Description                           |
|------------------------|--------------|---------------------------------------|
| prompt                 | Prompt      | Input to run CR on                    |
| openai_api_key         | OpenAI API Key | OpenAI API key for authentication     |
| username               | Username       | Username for Icosa API authentication |
| password               | Password | Password for Icosa API authentication |
| model_name             | Model Name      | OpenAI LLM to use for reason generation|

**Outputs**

| Name    | Display Name | Description                          |
|---------|-----------|--------------------------------------|
| optimized_prompt | Optimized Prompt| A message object containing the optimized prompt |
| reasons | Selected Reasons| A list of the selected reasons that are embedded in the optimized prompt|

</details>

## DuckDuckGo search

This component performs web searches using the [DuckDuckGo](https://www.duckduckgo.com) search engine with result-limiting capabilities.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Search Query | The search query to execute with DuckDuckGo. |
| max_results | Max Results | The maximum number of search results to return. Default: `5`. |
| max_snippet_length | Max Snippet Length | The maximum length of each result snippet. Default: `100`.|

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | [Data](/concepts-objects#data-object) | List of search results as Data objects containing snippets and full content. |
| text | Text | Search results formatted as a single text string. |

</details>

## Exa Search

This component provides an [https://exa.ai/](Exa Search) toolkit for search and content retrieval.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| metaphor_api_key | Exa Search API Key | API key for Exa Search (entered as a password) |
| use_autoprompt | Use Autoprompt | Whether to use autoprompt feature (default: true) |
| search_num_results | Search Number of Results | Number of results to return for search (default: 5) |
| similar_num_results | Similar Number of Results | Number of similar results to return (default: 5) |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| tools | Tools | List of search tools provided by the toolkit |

</details>

## Glean Search API

This component allows you to call the Glean Search API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| glean_api_url          | String       | URL of the Glean API                 |
| glean_access_token      | SecretString | Access token for Glean API authentication |
| query                  | String       | Search query input                    |
| page_size              | Integer      | Number of results per page (default: 10) |
| request_options        | Dict         | Additional options for the API request (optional) |

**Outputs**

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Glean Search tool for use in LangChain|

</details>

## Google Serper API

This component allows you to call the Serper.dev Google Search API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| serper_api_key         | SecretString | API key for Serper.dev authentication  |
| input_value            | String       | Search query input                    |
| k                      | Integer      | Number of search results to return    |

**Outputs**

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Google Serper search tool for use in LangChain|

</details>

## MCP server

This component connects to a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server and exposes the MCP server's tools as tools.

In addition to being an MCP client that can leverage MCP servers, Langflow is also an MCP server that exposes flows as tools through the `/api/v1/mcp/sse` API endpoint. For more information, see [MCP integrations](/integrations-mcp).

To use the MCP server component with an agent component, follow these steps:

1. Add the MCP server component to your workflow.
2. In the MCP server component, in the **MCP Command** field, enter the command to start your MCP server. For example, to start a [Fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) server, the command is:

```bash
uvx mcp-server-fetch
```

`uvx` is included with `uv` in the Langflow package.
To use `npx` server commands, you must first install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).
For an example of starting `npx` MCP servers, see [Connect an Astra DB MCP server to Langflow](/mcp-component-astra).

3. Click <Icon name="RefreshCw" aria-label="Refresh"/> to get the server's list of **Tools**.
4. In the **Tool** field, select the server tool you want the component to use.
The available fields change based on the selected tool.
For information on the parameters, see the MCP server's documentation.
5. In the MCP server component, enable **Tool mode**.
Connect the MCP server component's **Toolset** port to an **Agent** component's **Tools** port.

The flow looks similar to this:
![MCP server component](/img/mcp-server-component.png)

6. Open the **Playground**.
Ask the agent to summarize recent tech news. The agent calls the MCP server function `fetch` and returns the summary.
This confirms the MCP server is connected, and its tools are being used in Langflow.

For more information, see [MCP integrations](/integrations-mcp).

### MCP Server-Sent Events (SSE) mode

1. In the **MCP Server** component, select **SSE**.
A default address appears in the **MCP SSE URL** field.
2. In the **MCP SSE URL** field, modify the default address to point at the SSE endpoint of the Langflow server you're currently running.
The default value is `http://localhost:7860/api/v1/mcp/sse`.
3. In the **MCP Server** component, click <Icon name="RefreshCw" aria-label="Refresh"/> to retrieve the server's list of **Tools**.
4. Click the **Tools** field.
All of your flows are listed as tools.
5. Enable **Tool Mode**, and then connect the **MCP Server** component to an agent component's tool port.
The flow looks like this:
![MCP server component](/img/mcp-server-component-sse.png)
6. Open the **Playground** and chat with your tool.
The agent chooses the correct tool based on your query.

<details>
<summary>Parameters</summary>

**Inputs**

| Name    | Type   | Description                                |
|---------|--------|--------------------------------------------|
| command | String | MCP command (default: `uvx mcp-sse-shim@latest`) |

**Outputs**

| Name  | Type      | Description                               |
|-------|-----------|-------------------------------------------|
| tools | List[Tool]| List of tools exposed by the MCP server   |

</details>

## Wikidata

This component performs a search using the Wikidata API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| query | Query | The text query for similarity search on Wikidata. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The search results from Wikidata API as a list of Data objects. |
| text | Message | The search results formatted as a text message. |

</details>

## Legacy components

Legacy components are available to use but no longer supported.

### Calculator Tool

This component allows you to evaluate basic arithmetic expressions. It supports addition, subtraction, multiplication, division, and exponentiation.

<details>
<summary>Parameters</summary>

**Inputs**

| Name       | Type   | Description                                                        |
|------------|--------|--------------------------------------------------------------------|
| expression | String | The arithmetic expression to evaluate (for example, `4*4*(33/22)+12-20`). |

**Outputs**

| Name   | Type | Description                                     |
|--------|------|-------------------------------------------------|
| result | Tool | Calculator tool for use in LangChain            |

</details>

### Google Search API

This component allows you to call the Google Search API.

<details>
<summary>Parameters</summary>

**Inputs**

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| google_api_key         | SecretString | Google API key for authentication     |
| google_cse_id          | SecretString | Google Custom Search Engine ID        |
| input_value            | String       | Search query input                    |
| k                      | Integer      | Number of search results to return    |

**Outputs**

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Google Search tool for use in LangChain|

</details>

### Python Code Structured Tool

This component creates a structured tool from Python code using a dataclass.

The component dynamically updates its configuration based on the provided Python code, allowing for custom function arguments and descriptions.

<details>
<summary>Parameters</summary>

**Inputs**

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| tool_code              | String       | Python code for the tool's dataclass  |
| tool_name              | String       | Name of the tool                      |
| tool_description       | String       | Description of the tool               |
| return_direct          | Boolean      | Whether to return the function output directly |
| tool_function          | String       | Selected function for the tool        |
| global_variables        | Dict         | Global variables or data for the tool |

**Outputs**

| Name        | Type  | Description                             |
|-------------|-------|-----------------------------------------|
| result_tool  | Tool  │ Structured tool created from the Python code |

</details>

### Python REPL Tool

This component creates a Python REPL (Read-Eval-Print Loop) tool for executing Python code.

<details>
<summary>Parameters</summary>

**Inputs**

| Name            | Type         | Description                                             |
|-----------------|--------------|--------------------------------------------------------|
| name            | String       | The name of the tool (default: "python_repl")          |
| description     | String       | A description of the tool's functionality               |
| global_imports  | List[String] | List of modules to import globally (default: ["math"])  |

**Outputs**

| Name | Type | Description                                |
|------|------|--------------------------------------------|
| tool | Tool | Python REPL tool for use in LangChain      |

</details>

### Retriever Tool

This component creates a tool for interacting with a retriever in LangChain.

<details>
<summary>Parameters</summary>

**Inputs**

| Name        | Type          | Description                                 |
|-------------|---------------|---------------------------------------------|
| retriever   | BaseRetriever | The retriever to interact with              |
| name        | String        | The name of the tool                        |
| description | String        | A description of the tool's functionality   |

**Outputs**

| Name | Type | Description                                |
|------|------|--------------------------------------------|
| tool | Tool | Retriever tool for use in LangChain        |

</details>

### Search API

This component calls the `searchapi.io` API. It can be used to search the web for information.

For more information, see the [SearchAPI documentation](https://www.searchapi.io/docs/google).

<details>
<summary>Parameters</summary>

**Inputs**

| Name           | Display Name       | Info                                                |
|----------------|---------------------|-----------------------------------------------------|
| engine         | Engine              | The search engine to use (default: "google")        |
| api_key        | SearchAPI API Key   | The API key for authenticating with SearchAPI       |
| input_value    | Input               | The search query or input for the API call          |
| search_params  | Search parameters   | Additional parameters for customizing the search    |

**Outputs**

| Name | Display Name    | Info                                                 |
|------|-----------------|------------------------------------------------------|
| data | Search Results  | List of Data objects containing search results       |
| tool | Search API Tool | A Tool object for use in LangChain workflows         |

</details>


### SearXNG Search Tool

This component creates a tool for searching using SearXNG, a metasearch engine.

<details>
<summary>Parameters</summary>

**Inputs**

| Name        | Type         | Description                           |
|-------------|--------------|---------------------------------------|
| url         | String       | The URL of the SearXNG instance       |
| max_results | Integer      | Maximum number of results to return   |
| categories  | List[String] | Categories to search in               |
| language    | String       | Language for the search results       |

**Outputs**

| Name        | Type | Description                                |
|-------------|------|--------------------------------------------|
| result_tool | Tool | SearXNG search tool for use in LangChain   |

</details>

### Wikipedia API

This component creates a tool for searching and retrieving information from Wikipedia.

<details>
<summary>Parameters</summary>

**Inputs**

| Name                    | Type    | Description                                                |
|-------------------------|---------|-----------------------------------------------------------|
| input_value             | String  | Search query input                                         |
| lang                    | String  | Language code for Wikipedia (default: "en")                |
| k                       | Integer | Number of results to return                                |
| load_all_available_meta | Boolean | Whether to load all available metadata (advanced)          |
| doc_content_chars_max   | Integer | Maximum number of characters for document content (advanced)|

**Outputs**

| Name    | Type      | Description                           |
|---------|-----------|---------------------------------------|
| results | List[Data]| List of Wikipedia search results      |
| tool    | Tool      | Wikipedia search tool for use in LangChain |

</details>

## Deprecated components

Deprecated components have been replaced by newer alternatives and should not be used in new projects.

### MCP Tools (stdio)
:::important
This component is deprecated as of Langflow version 1.3.
Instead, use the [MCP server component](/components-tools#mcp-server)
:::


### MCP Tools (SSE)
:::important
This component is deprecated as of Langflow version 1.3.
Instead, use the [MCP server component](/components-tools#mcp-server)
:::

