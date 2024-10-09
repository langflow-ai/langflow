# Agents

Agent components are used to define the behavior and capabilities of AI agents in your flow. Agents can interact with APIs, databases, and other services, but can also use LLMs as a reasoning engine to decide which course to take in your flow.

## CSV Agent

This component creates a CSV agent from a CSV file and LLM.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| path | File | Path to the CSV file |
| agent_type | String | Type of agent to create (zero-shot-react-description, openai-functions, or openai-tools) |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | CSV agent instance |

## CrewAI Agent

This component represents an Agent of CrewAI, allowing for the creation of specialized AI agents with defined roles, goals, and capabilities within a crew.

For more information, see the [CrewAI documentation](https://docs.crewai.com/core-concepts/Agents/).

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| role | Role | The role of the agent |
| goal | Goal | The objective of the agent |
| backstory | Backstory | The backstory of the agent |
| tools | Tools | Tools at agent's disposal |
| llm | Language Model | Language model that will run the agent |
| memory | Memory | Whether the agent should have memory or not |
| verbose | Verbose | Enables verbose output |
| allow_delegation | Allow Delegation | Whether the agent is allowed to delegate tasks to other agents |
| allow_code_execution | Allow Code Execution | Whether the agent is allowed to execute code |
| kwargs | kwargs | Additional keyword arguments for the agent |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| output | Agent | The constructed CrewAI Agent object |

## Hierarchical Crew

This component represents a group of agents, managing how they should collaborate and the tasks they should perform in a hierarchical structure. This component allows for the creation of a crew with a manager overseeing the task execution.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Hierarchical/).

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| agents | Agents | List of Agent objects representing the crew members |
| tasks | Tasks | List of HierarchicalTask objects representing the tasks to be executed |
| manager_llm | Manager LLM | Language model for the manager agent (optional) |
| manager_agent | Manager Agent | Specific agent to act as the manager (optional) |
| verbose | Verbose | Enables verbose output for detailed logging |
| memory | Memory | Specifies the memory configuration for the crew |
| use_cache | Use Cache | Enables caching of results |
| max_rpm | Max RPM | Sets the maximum requests per minute |
| share_crew | Share Crew | Determines if the crew information is shared among agents |
| function_calling_llm | Function Calling LLM | Specifies the language model for function calling |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| crew | Crew | The constructed Crew object with hierarchical task execution |

## JSON Agent

This component creates a JSON agent from a JSON or YAML file and an LLM.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| path | File | Path to the JSON or YAML file |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | JSON agent instance |

## OpenAI Tools Agent

This component creates an OpenAI Tools Agent using LangChain.

For more information, see the [LangChain documentation](https://python.langchain.com/v0.1/docs/modules/agents/agent_types/openai_tools/).

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent (must be tool-enabled) |
| system_prompt | String | System prompt for the agent |
| user_prompt | String | User prompt template (must contain 'input' key) |
| chat_history | List[Data] | Optional chat history for the agent |
| tools | List[Tool] | List of tools available to the agent |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | OpenAI Tools Agent instance |

## OpenAPI Agent

This component creates an OpenAPI Agent to interact with APIs defined by OpenAPI specifications.

For more information, see the LangChain documentation on OpenAPI Agents.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| path | File | Path to the OpenAPI specification file (JSON or YAML) |
| allow_dangerous_requests | Boolean | Whether to allow potentially dangerous API requests |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | OpenAPI Agent instance |

## SQL Agent

This component creates a SQL Agent to interact with SQL databases.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| database_uri | String | URI of the SQL database to connect to |
| extra_tools | List[Tool] | Additional tools to provide to the agent (optional) |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | SQL Agent instance |

## Sequential Crew

This component represents a group of agents with tasks that are executed sequentially. This component allows for the creation of a crew that performs tasks in a specific order.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Sequential/).

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| tasks | Tasks | List of SequentialTask objects representing the tasks to be executed |
| verbose | Verbose | Enables verbose output for detailed logging |
| memory | Memory | Specifies the memory configuration for the crew |
| use_cache | Use Cache | Enables caching of results |
| max_rpm | Max RPM | Sets the maximum requests per minute |
| share_crew | Share Crew | Determines if the crew information is shared among agents |
| function_calling_llm | Function Calling LLM | Specifies the language model for function calling |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| crew | Crew | The constructed Crew object with sequential task execution |

## Sequential task agent

This component creates a CrewAI Task and its associated Agent, allowing for the definition of sequential tasks with specific agent roles and capabilities.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Sequential/).

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| role | Role | The role of the agent |
| goal | Goal | The objective of the agent |
| backstory | Backstory | The backstory of the agent |
| tools | Tools | Tools at agent's disposal |
| llm | Language Model | Language model that will run the agent |
| memory | Memory | Whether the agent should have memory or not |
| verbose | Verbose | Enables verbose output |
| allow_delegation | Allow Delegation | Whether the agent is allowed to delegate tasks to other agents |
| allow_code_execution | Allow Code Execution | Whether the agent is allowed to execute code |
| agent_kwargs | Agent kwargs | Additional kwargs for the agent |
| task_description | Task Description | Descriptive text detailing task's purpose and execution |
| expected_output | Expected Task Output | Clear definition of expected task outcome |
| async_execution | Async Execution | Boolean flag indicating asynchronous task execution |
| previous_task | Previous Task | The previous task in the sequence (for chaining) |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| task_output | Sequential Task | List of SequentialTask objects representing the created task(s) |

## Tool Calling Agent

This component creates a Tool Calling Agent using LangChain.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| system_prompt | String | System prompt for the agent |
| user_prompt | String | User prompt template (must contain 'input' key) |
| chat_history | List[Data] | Optional chat history for the agent |
| tools | List[Tool] | List of tools available to the agent |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | Tool Calling Agent instance |

## Vector Store Agent

This component creates a Vector Store Agent using LangChain.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| vectorstore | VectorStoreInfo | Vector store information for the agent to use |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | Vector Store Agent instance |

## Vector Store Router Agent

This component creates a Vector Store Router Agent using LangChain.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| vectorstores | List[VectorStoreInfo] | List of vector store information for the agent to route between |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | Vector Store Router Agent instance |

## XML Agent

This component creates an XML Agent using LangChain.

The agent uses XML formatting for tool instructions to the Language Model.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | Language model to use for the agent |
| user_prompt | String | Custom prompt template for the agent (includes XML formatting instructions) |
| tools | List[Tool] | List of tools available to the agent |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | XML Agent instance |