# Tools

Tool components are used to interact with external services, APIs, and tools. They can be used to search the web, query databases, and perform other tasks.

## Bing Search API

This component allows you to call the Bing Search API.

### Parameters

#### Inputs

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| bing_subscription_key   | SecretString | Bing API subscription key             |
| input_value            | String       | Search query input                    |
| bing_search_url        | String       | Custom Bing Search URL (optional)    |
| k                      | Integer      | Number of search results to return    |

#### Outputs

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Bing Search tool for use in LangChain|

## Calculator Tool

This component creates a tool for performing basic arithmetic operations on a given expression.

### Parameters

#### Inputs

| Name       | Type   | Description                                                        |
|------------|--------|--------------------------------------------------------------------|
| expression | String | The arithmetic expression to evaluate (e.g., `4*4*(33/22)+12-20`). |

#### Outputs

| Name   | Type | Description                                     |
|--------|------|-------------------------------------------------|
| result | Tool | Calculator tool for use in LangChain            |

This component allows you to evaluate basic arithmetic expressions. It supports addition, subtraction, multiplication, division, and exponentiation. The tool uses a secure evaluation method that prevents the execution of arbitrary Python code.

## Combinatorial Reasoner

This component runs Icosa's Combinatorial Reasoning (CR) pipeline on an input to create an optimized prompt with embedded reasons. Sign up for access here: https://forms.gle/oWNv2NKjBNaqqvCx6 

### Parameters

#### Inputs
| Name                   | Display Name | Description                           |
|------------------------|--------------|---------------------------------------|
| prompt                 | Prompt      | Input to run CR on                    |
| openai_api_key         | OpenAI API Key | OpenAI API key for authentication     |
| username               | Username       | Username for Icosa API authentication |
| password               | Password | Password for Icosa API authentication |
| model_name             | Model Name      | OpenAI LLM to use for reason generation|

#### Outputs

| Name    | Display Name | Description                          |
|---------|-----------|--------------------------------------|
| optimized_prompt | Optimized Prompt| A message object containing the optimized prompt |
| reasons | Selected Reasons| A list of the selected reasons that are embedded in the optimized prompt|

## Glean Search API

This component allows you to call the Glean Search API.

### Parameters

#### Inputs

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| glean_api_url          | String       | URL of the Glean API                 |
| glean_access_token      | SecretString | Access token for Glean API authentication |
| query                  | String       | Search query input                    |
| page_size              | Integer      | Number of results per page (default: 10) |
| request_options        | Dict         | Additional options for the API request (optional) |

#### Outputs

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Glean Search tool for use in LangChain|

## Google Search API

This component allows you to call the Google Search API.

### Parameters

#### Inputs

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| google_api_key         | SecretString | Google API key for authentication     |
| google_cse_id          | SecretString | Google Custom Search Engine ID        |
| input_value            | String       | Search query input                    |
| k                      | Integer      | Number of search results to return    |

#### Outputs

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Google Search tool for use in LangChain|

## Google Serper API

This component allows you to call the Serper.dev Google Search API.

### Parameters

#### Inputs

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| serper_api_key         | SecretString | API key for Serper.dev authentication  |
| input_value            | String       | Search query input                    |
| k                      | Integer      | Number of search results to return    |

#### Outputs

| Name    | Type      | Description                          |
|---------|-----------|--------------------------------------|
| results | List[Data]| List of search results               |
| tool    | Tool      | Google Serper search tool for use in LangChain|

## Python Code Structured Tool

This component creates a structured tool from Python code using a dataclass.

The component dynamically updates its configuration based on the provided Python code, allowing for custom function arguments and descriptions.

### Parameters

#### Inputs

| Name                   | Type         | Description                           |
|------------------------|--------------|---------------------------------------|
| tool_code              | String       | Python code for the tool's dataclass  |
| tool_name              | String       | Name of the tool                      |
| tool_description       | String       | Description of the tool               |
| return_direct          | Boolean      | Whether to return the function output directly |
| tool_function          | String       | Selected function for the tool        |
| global_variables        | Dict         | Global variables or data for the tool |

#### Outputs

| Name        | Type  | Description                             |
|-------------|-------|-----------------------------------------|
| result_tool  | Tool  │ Structured tool created from the Python code |

## Python REPL Tool

This component creates a Python REPL (Read-Eval-Print Loop) tool for executing Python code.

### Parameters

#### Inputs

| Name            | Type         | Description                                             |
|-----------------|--------------|--------------------------------------------------------|
| name            | String       | The name of the tool (default: "python_repl")          |
| description     | String       | A description of the tool's functionality               |
| global_imports  | List[String] | List of modules to import globally (default: ["math"])  |

#### Outputs

| Name | Type | Description                                |
|------|------|--------------------------------------------|
| tool | Tool | Python REPL tool for use in LangChain      |

## Retriever Tool

This component creates a tool for interacting with a retriever in LangChain.

### Parameters

#### Inputs

| Name        | Type          | Description                                 |
|-------------|---------------|---------------------------------------------|
| retriever   | BaseRetriever | The retriever to interact with              |
| name        | String        | The name of the tool                        |
| description | String        | A description of the tool's functionality   |

#### Outputs

| Name | Type | Description                                |
|------|------|--------------------------------------------|
| tool | Tool | Retriever tool for use in LangChain        |

## SearXNG Search Tool

This component creates a tool for searching using SearXNG, a metasearch engine.

### Parameters

#### Inputs

| Name        | Type         | Description                           |
|-------------|--------------|---------------------------------------|
| url         | String       | The URL of the SearXNG instance       |
| max_results | Integer      | Maximum number of results to return   |
| categories  | List[String] | Categories to search in               |
| language    | String       | Language for the search results       |

#### Outputs

| Name        | Type | Description                                |
|-------------|------|--------------------------------------------|
| result_tool | Tool | SearXNG search tool for use in LangChain   |

## Search API

This component calls the `searchapi.io` API. It can be used to search the web for information.

For more information, see the [SearchAPI documentation](https://www.searchapi.io/docs/google).

### Parameters

#### Inputs

| Name           | Display Name       | Info                                                |
|----------------|---------------------|-----------------------------------------------------|
| engine         | Engine              | The search engine to use (default: "google")        |
| api_key        | SearchAPI API Key   | The API key for authenticating with SearchAPI       |
| input_value    | Input               | The search query or input for the API call          |
| search_params  | Search parameters   | Additional parameters for customizing the search    |

#### Outputs

| Name | Display Name    | Info                                                 |
|------|-----------------|------------------------------------------------------|
| data | Search Results  | List of Data objects containing search results       |
| tool | Search API Tool | A Tool object for use in LangChain workflows         |

## Serp Search API

This component creates a tool for searching using the Serp API.

### Parameters

#### Inputs

| Name             | Type         | Description                                 |
|------------------|--------------|---------------------------------------------|
| serpapi_api_key  | SecretString | API key for Serp API authentication         |
| input_value      | String       | Search query input                          |
| search_params    | Dict         | Additional search parameters (optional)     |

#### Outputs

| Name    | Type      | Description                                 |
|---------|-----------|---------------------------------------------|
| results | List[Data]| List of search results                      |
| tool    | Tool      | Serp API search tool for use in LangChain   |

## Wikipedia API

This component creates a tool for searching and retrieving information from Wikipedia.

### Parameters

#### Inputs

| Name                    | Type    | Description                                                |
|-------------------------|---------|-----------------------------------------------------------|
| input_value             | String  | Search query input                                         |
| lang                    | String  | Language code for Wikipedia (default: "en")                |
| k                       | Integer | Number of results to return                                |
| load_all_available_meta | Boolean | Whether to load all available metadata (advanced)          |
| doc_content_chars_max   | Integer | Maximum number of characters for document content (advanced)|

#### Outputs

| Name    | Type      | Description                           |
|---------|-----------|---------------------------------------|
| results | List[Data]| List of Wikipedia search results      |
| tool    | Tool      | Wikipedia search tool for use in LangChain |

## Wolfram Alpha API

This component creates a tool for querying the Wolfram Alpha API.

### Parameters

#### Inputs

| Name        | Type         | Description                    |
|-------------|--------------|--------------------------------|
| input_value | String       | Query input for Wolfram Alpha  |
| app_id      | SecretString | Wolfram Alpha API App ID       |

#### Outputs

| Name    | Type      | Description                                    |
|---------|-----------|------------------------------------------------|
| results | List[Data]| List containing the Wolfram Alpha API response |
| tool    | Tool      | Wolfram Alpha API tool for use in LangChain    |

## Yahoo Finance News Tool

This component creates a tool for retrieving news from Yahoo Finance.

### Parameters

This component does not have any input parameters.

#### Outputs

| Name | Type | Description                                  |
|------|------|----------------------------------------------|
| tool | Tool | Yahoo Finance News tool for use in LangChain |


## Astra DB Tool

The `Astra DB Tool` allows agents to connect to and query data from Astra DB Collections.

### Parameters

#### Inputs

| Name              | Type   | Description                                                                                                                      |
|-------------------|--------|----------------------------------------------------------------------------------------------------------------------------------|
| Tool Name         | String | The name used to reference the tool in the agent's prompt.                                                                       |
| Tool Description  | String | A brief description of the tool. This helps the model decide when to use it.                                                     |
| Collection Name   | String | The name of the Astra DB collection to query.                                                                                    |
| Token             | SecretString | The authentication token for accessing Astra DB.                                                                                 |
| API Endpoint      | String | The Astra DB API endpoint.                                                                                                       |
| Projection Fields | String | The attributes to return, separated by commas. Default: "*".                                                                     |
| Tool Parameters   | Dict   | Parameters the model needs to fill to execute the tool. For required parameters, use an exclamation mark (e.g., "!customer_id"). |
| Static Filters    | Dict   | Attribute-value pairs used to filter query results.                                                                              |
| Limit             | String | The number of documents to return.                                                                                               |



## Astra DB CQL Tool

The `Astra DB CQL Tool` allows agents to query data from CQL Tables in Astra DB.

### Parameters

#### Inputs

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
| Clustering Keys   | Dict   | Optional parameters the model can fill to refine the query. Required parameters should be marked with an  exclamation mark (e.g., "!customer_id"). |
| Static Filters    | Dict   | Attribute-value pairs used to filter query results.                                                                                                |
| Limit             | String | The number of records to return.                                                                                                                   |
