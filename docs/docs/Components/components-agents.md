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

The [simple agent starter project](/docs/simple-agent) uses an [agent component](#agent-component) connected to URL and Calculator tools to answer a user's questions. The OpenAI LLM acts as a brain for the agent to decide which tool to use. Tools are connected to agent components at the **Tools** port.

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

For a multi-agent example see [Create a flow with an agent](/docs/agents).

## Agent component {#agent-component}

This component creates an agent that can use tools to answer questions and perform tasks based on given instructions.

The component includes an LLM model integration, a system message prompt, and a **Tools** port to connect tools to extend its capabilities.

For more information on this component, see the [Agent documentation](/docs/agents).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| agent_llm | Dropdown | The provider of the language model that the agent uses to generate responses. Options include OpenAI and other providers or Custom. |
| system_prompt | String | The system prompt provides initial instructions and context to guide the agent's behavior. |
| tools | List | The list of tools available for the agent to use. This field is optional and can be empty. |
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