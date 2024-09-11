---
title: Prompts
sidebar_position: 2
slug: /components-prompts
---

# Prompts

A prompt serves as the input to a language model, comprising multiple components that can be parameterized using prompt templates.

Prompt templates provide a systematic approach for generating prompts, allowing for reproducible customization through defined input variables.

## Prompt

This component creates a prompt template with dynamic variables. It is useful for structuring prompts and passing dynamic data to a language model.

If you have a template like `Hello {name}, how are you?`, a new field called `name` will be created.

### Parameters

| Name     | Display Name | Info                                                                    |
|----------|--------------|-------------------------------------------------------------------------|
| Template | Template     | The template for the prompt. Creates dynamic fields using `{variable_name}` |

## Langchain Hub Prompt Template

This component fetches prompts from the [Langchain Hub](https://docs.smith.langchain.com/old/category/prompt-hub).

When a prompt is loaded, the component generates input fields for custom variables. For example, the default prompt "efriis/my-first-prompt" generates fields for `profession` and `question`.

### Parameters

| Name                  | Display Name            | Info                                                   |
|-----------------------|-------------------------|--------------------------------------------------------|
| langchain_api_key     | LangChain API Key       | SecretStrInput for user's LangChain API key            |
| langchain_hub_prompt  | LangChain Hub Prompt    | StrInput specifying the LangChain Hub prompt to use    |
