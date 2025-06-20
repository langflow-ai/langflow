---
title: Agents
slug: /components-agents
---

# Agent components in Langflow

Agent components define the behavior and capabilities of AI agents in your flow.

Agents use LLMs as a reasoning engine to decide which of the connected tool components to use to solve a problem.

Tools in agentic functions are essentially functions that the agent can call to perform tasks or access external resources.
A function is wrapped as a `Tool` object with a common interface the agent understands.
Agents become aware of tools through tool registration where the agent is provided a list of available tools typically at agent initialization. The `Tool` object's description tells the agent what the tool can do.

The agent then uses a connected LLM to reason through the problem to decide which tool is best for the job.

## Use an agent in a flow

The [simple agent starter project](/simple-agent) uses an [agent component](#agent-component) connected to URL and Calculator tools to answer a user's questions. The OpenAI LLM acts as a brain for the agent to decide which tool to use. Tools are connected to agent components at the **Tools** port.

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

For a multi-agent example see, [Create a problem-solving agent](/agents-tool-calling-agent-component).

## Agent component {#agent-component}

This component creates an agent that can use tools to answer questions and perform tasks based on given instructions.

The component includes an LLM model integration, a system message prompt, and a **Tools** port to connect tools to extend its capabilities.

For more information on this component, see the [tool calling agent documentation](/agents-tool-calling-agent-component).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| agent_llm | Dropdown | The provider of the language model that the agent uses to generate responses. Options include OpenAI and other providers or Custom. |
| system_prompt | String | The system prompt provides initial instructions and context to guide the agent's behavior. |
| tools | List | The list of tools available for the agent to use. |
| input_value | String | The input task or question for the agent to process. |
| add_current_date_tool | Boolean | When true this adds a tool to the agent that returns the current date. |
| memory | Memory | An optional memory configuration for maintaining conversation history. |
| max_iterations | Integer | The maximum number of iterations the agent can perform. |
| handle_parsing_errors | Boolean | This determines whether to handle parsing errors during agent execution. |
| verbose | Boolean | This enables verbose output for detailed logging. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| response | Message | The agent's response to the given input task. |

</details>

## Legacy components

**Legacy** components are available for use but are no longer supported.

### JSON Agent

This component creates a JSON agent from a JSON or YAML file and an LLM.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use for the agent. |
| path | File | The path to the JSON or YAML file. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The JSON agent instance. |

</details>

### Vector Store Agent

This component creates a Vector Store Agent using LangChain.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use for the agent. |
| vectorstore | VectorStoreInfo | The vector store information for the agent to use. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The Vector Store Agent instance. |

</details>

### Vector Store Router Agent

This component creates a Vector Store Router Agent using LangChain.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use for the agent. |
| vectorstores | List[VectorStoreInfo] | The list of vector store information for the agent to route between. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The Vector Store Router Agent instance. |

</details>

## Moved components

The following components are available under **Bundles**.

### CrewAI Agent

This component represents an Agent of CrewAI allowing for the creation of specialized AI agents with defined roles goals and capabilities within a crew.

For more information, see the [CrewAI documentation](https://docs.crewai.com/core-concepts/Agents/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| role | Role | The role of the agent. |
| goal | Goal | The objective of the agent. |
| backstory | Backstory | The backstory of the agent. |
| tools | Tools | The tools at the agent's disposal. |
| llm | Language Model | The language model that runs the agent. |
| memory | Memory | This determines whether the agent should have memory or not. |
| verbose | Verbose | This enables verbose output. |
| allow_delegation | Allow Delegation | This determines whether the agent is allowed to delegate tasks to other agents. |
| allow_code_execution | Allow Code Execution | This determines whether the agent is allowed to execute code. |
| kwargs | kwargs | Additional keyword arguments for the agent. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| output | Agent | The constructed CrewAI Agent object. |

</details>

### Hierarchical Crew

This component represents a group of agents managing how they should collaborate and the tasks they should perform in a hierarchical structure. This component allows for the creation of a crew with a manager overseeing the task execution.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Hierarchical/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| agents | Agents | The list of Agent objects representing the crew members. |
| tasks | Tasks | The list of HierarchicalTask objects representing the tasks to be executed. |
| manager_llm | Manager LLM | The language model for the manager agent. |
| manager_agent | Manager Agent | The specific agent to act as the manager. |
| verbose | Verbose | This enables verbose output for detailed logging. |
| memory | Memory | The memory configuration for the crew. |
| use_cache | Use Cache | This enables caching of results. |
| max_rpm | Max RPM | This sets the maximum requests per minute. |
| share_crew | Share Crew | This determines if the crew information is shared among agents. |
| function_calling_llm | Function Calling LLM | The language model for function calling. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| crew | Crew | The constructed Crew object with hierarchical task execution. |

</details>

### CSV Agent

This component creates a CSV agent from a CSV file and LLM.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use for the agent. |
| path | File | The path to the CSV file. |
| agent_type | String | The type of agent to create. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The CSV agent instance. |

</details>

### OpenAI Tools Agent

This component creates an OpenAI Tools Agent.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| tools | List of Tools | The tools to give the agent access to. |
| system_prompt | String | The system prompt to provide context to the agent. |
| input_value | String | The user's input to the agent. |
| memory | Memory | The memory for the agent to use for context persistence. |
| max_iterations | Integer | The maximum number of iterations to allow the agent to execute. |
| verbose | Boolean | This determines whether to print out the agent's intermediate steps. |
| handle_parsing_errors | Boolean | This determines whether to handle parsing errors in the agent. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The OpenAI Tools agent instance. |
| output | String | The output from executing the agent on the input. |

</details>

### OpenAPI Agent

This component creates an agent for interacting with OpenAPI services.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| openapi_spec | String | The OpenAPI specification for the service. |
| base_url | String | The base URL for the API. |
| headers | Dict | The optional headers for API requests. |
| agent_executor_kwargs | Dict | The optional parameters for the agent executor. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The OpenAPI agent instance. |

</details>

### Sequential Crew

This component represents a group of agents with tasks that are executed sequentially. This component allows for the creation of a crew that performs tasks in a specific order.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Sequential/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| tasks | Tasks | The list of SequentialTask objects representing the tasks to be executed. |
| verbose | Verbose | This enables verbose output for detailed logging. |
| memory | Memory | The memory configuration for the crew. |
| use_cache | Use Cache | This enables caching of results. |
| max_rpm | Max RPM | This sets the maximum requests per minute. |
| share_crew | Share Crew | This determines if the crew information is shared among agents. |
| function_calling_llm | Function Calling LLM | The language model for function calling. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| crew | Crew | The constructed Crew object with sequential task execution. |

</details>

### Sequential task agent

This component creates a CrewAI Task and its associated Agent allowing for the definition of sequential tasks with specific agent roles and capabilities.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Sequential/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| role | Role | The role of the agent. |
| goal | Goal | The objective of the agent. |
| backstory | Backstory | The backstory of the agent. |
| tools | Tools | The tools at the agent's disposal. |
| llm | Language Model | The language model that runs the agent. |
| memory | Memory | This determines whether the agent should have memory or not. |
| verbose | Verbose | This enables verbose output. |
| allow_delegation | Allow Delegation | This determines whether the agent is allowed to delegate tasks to other agents. |
| allow_code_execution | Allow Code Execution | This determines whether the agent is allowed to execute code. |
| agent_kwargs | Agent kwargs | The additional kwargs for the agent. |
| task_description | Task Description | The descriptive text detailing the task's purpose and execution. |
| expected_output | Expected Task Output | The clear definition of the expected task outcome. |
| async_execution | Async Execution | The boolean flag indicating asynchronous task execution. |
| previous_task | Previous Task | The previous task in the sequence for chaining. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| task_output | Sequential Task | The list of SequentialTask objects representing the created tasks. |

</details>

### SQL Agent

This component creates an agent for interacting with SQL databases.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| database | Database | The SQL database connection. |
| top_k | Integer | The number of results to return from a SELECT query. |
| use_tools | Boolean | This determines whether to use tools for query execution. |
| return_intermediate_steps | Boolean | This determines whether to return the agent's intermediate steps. |
| max_iterations | Integer | The maximum number of iterations to run the agent. |
| max_execution_time | Integer | The maximum execution time in seconds. |
| early_stopping_method | String | The method to use for early stopping. |
| verbose | Boolean | This determines whether to print the agent's thoughts. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The SQL agent instance. |

</details>

### Tool Calling Agent

This component creates an agent for structured tool calling with various language models.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| tools | List[Tool] | The list of tools available to the agent. |
| system_message | String | The system message to use for the agent. |
| return_intermediate_steps | Boolean | This determines whether to return the agent's intermediate steps. |
| max_iterations | Integer | The maximum number of iterations to run the agent. |
| max_execution_time | Integer | The maximum execution time in seconds. |
| early_stopping_method | String | The method to use for early stopping. |
| verbose | Boolean | This determines whether to print the agent's thoughts. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The tool calling agent instance. |

</details>

### XML Agent

This component creates an XML Agent using LangChain.

The agent uses XML formatting for tool instructions to the Language Model.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use for the agent. |
| user_prompt | String | The custom prompt template for the agent with XML formatting instructions. |
| tools | List[Tool] | The list of tools available to the agent. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The XML Agent instance. |

</details>