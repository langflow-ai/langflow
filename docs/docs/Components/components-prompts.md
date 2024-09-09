---
title: Prompts
sidebar_position: 2
slug: /components-prompts
---

A prompt is the input provided to a language model, consisting of multiple components and can be parameterized using prompt templates. A prompt template offers a reproducible method for generating prompts, enabling easy customization through input variables.

### Prompt {#c852d1761e6c46b19ce72e5f7c70958c}

This component creates a prompt template with dynamic variables. This is useful for structuring prompts and passing dynamic data to a language model.

**Parameters**

- **Template:** The template for the prompt. This field allows you to create other fields dynamically by using curly brackets `{}`. For example, if you have a template like `Hello {name}, how are you?`, a new field called `name` will be created. Prompt variables can be created with any name inside curly brackets, e.g. `{variable_name}`.

### Langchain Hub Prompt Template {#6e32412f062b42efbdf56857eafb3651}

This component fetches prompts from the Langchain Hub.

**Parameters**

- **langchain_api_key**: A SecretStrInput that requires the user's LangChain API key for authentication

- **langchain_hub_prompt**: A StrInput that specifies the LangChain Hub prompt to use. When a prompt is loaded, the component generates input fields for custom variables. You can see how the component generates `profession` and `question` fields for the `efriis/my-first-prompt` default prompt.
