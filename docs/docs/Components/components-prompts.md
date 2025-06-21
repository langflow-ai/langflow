---
title: Prompts
slug: /components-prompts
---

# Prompt components in Langflow

A prompt is a structured input to a language model that instructs the model how to handle user inputs and variables.

Prompt components create prompt templates with custom fields and dynamic variables for providing your model structured, repeatable prompts.

Prompts are a combination of natural language and variables created with curly braces.

## Use a prompt component in a flow

An example of modifying a prompt can be found in [Vector RAG starter flow](/vector-store-rag), where a basic chatbot flow is extended to include a full vector RAG pipeline.

![Vector RAG connected to a chatbot](/img/starter-flow-vector-rag.png)

The default prompt in the **Prompt** component is `Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.`

This prompt creates a "personality" for your LLM's chat interactions, but it doesn't include variables that you may find useful when templating prompts.

To modify the prompt template, in the **Prompt** component, click the **Template** field. For example, the `{context}` variable gives the LLM model access to embedded vector data to return better answers.

```text
Given the context
{context}
Answer the question
{user_question}
```

When variables are added to a prompt template, new fields are automatically created in the component. These fields can be connected to receive text input from other components to automate prompting, or to output instructions to other components. An example of prompts controlling agents behavior is available in the [sequential tasks agent starter flow](/sequential-agent).

<details>
<summary>Parameters</summary>

**Inputs**

| Name     | Display Name | Info                                                              |
|----------|--------------|-------------------------------------------------------------------|
| template | Template     | Create a prompt template with dynamic variables.                  |

**Outputs**

| Name   | Display Name    | Info                                                   |
|--------|----------------|--------------------------------------------------------|
| prompt | Prompt Message  | The built prompt message returned by the `build_prompt` method. |

</details>

## Langchain Hub Prompt Template

:::important
This component is available in the **Components** menu under **Bundles**.
:::

This component fetches prompts from the [Langchain Hub](https://docs.smith.langchain.com/old/category/prompt-hub).

When a prompt is loaded, the component generates input fields for custom variables. For example, the default prompt "efriis/my-first-prompt" generates fields for `profession` and `question`.

<details>
<summary>Parameters</summary>

**Inputs**

| Name               | Display Name              | Info                                    |
|--------------------|---------------------------|------------------------------------------|
| langchain_api_key  | Your LangChain API Key    | The LangChain API Key to use.            |
| langchain_hub_prompt| LangChain Hub Prompt     | The LangChain Hub prompt to use.         |

**Outputs**

| Name   | Display Name | Info                                                              |
|--------|--------------|-------------------------------------------------------------------|
| prompt | Build Prompt | The built prompt message returned by the `build_prompt` method.   |

</details>
