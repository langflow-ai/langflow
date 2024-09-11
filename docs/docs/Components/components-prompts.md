---
title: Prompts
sidebar_position: 2
slug: /components-prompts
---

# Prompts

A prompt serves as the input to a language model, comprising multiple components that can be parameterized using prompt templates.

Prompt templates provide a systematic approach for generating prompts, allowing for reproducible customization through defined input variables.

### Parameters

#### Inputs

| Name     | Display Name | Info                                                              |
|----------|--------------|-------------------------------------------------------------------|
| template | Template     | Create a prompt template with dynamic variables.                  |

#### Outputs

| Name   | Display Name    | Info                                                   |
|--------|----------------|--------------------------------------------------------|
| prompt | Prompt Message  | The built prompt message returned by the `build_prompt` method. |

## Langchain Hub Prompt Template

This component fetches prompts from the [Langchain Hub](https://docs.smith.langchain.com/old/category/prompt-hub).

When a prompt is loaded, the component generates input fields for custom variables. For example, the default prompt "efriis/my-first-prompt" generates fields for `profession` and `question`.

### Parameters

#### Inputs

| Name               | Display Name              | Info                                    |
|--------------------|---------------------------|------------------------------------------|
| langchain_api_key  | Your LangChain API Key    | The LangChain API Key to use.            |
| langchain_hub_prompt| LangChain Hub Prompt     | The LangChain Hub prompt to use.         |

#### Outputs

| Name   | Display Name | Info                                                              |
|--------|--------------|-------------------------------------------------------------------|
| prompt | Build Prompt | The built prompt message returned by the `build_prompt` method.   |
