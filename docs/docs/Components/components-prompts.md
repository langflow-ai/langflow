---
title: Prompts
sidebar_position: 2
slug: /components-prompts
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




A prompt is the input provided to a language model, consisting of multiple components and can be parameterized using prompt templates. A prompt template offers a reproducible method for generating prompts, enabling easy customization through input variables.


### Prompt {#c852d1761e6c46b19ce72e5f7c70958c}


This component creates a prompt template with dynamic variables. This is useful for structuring prompts and passing dynamic data to a language model.


**Parameters**

- **Template:** The template for the prompt. This field allows you to create other fields dynamically by using curly brackets `{}`. For example, if you have a template like `Hello {name}, how are you?`, a new field called `name` will be created. Prompt variables can be created with any name inside curly brackets, e.g. `{variable_name}`.

### PromptTemplate {#6e32412f062b42efbdf56857eafb3651}


The `PromptTemplate` component enables users to create prompts and define variables that control how the model is instructed. Users can input a set of variables which the template uses to generate the prompt when a conversation starts.


After defining a variable in the prompt template, it acts as its own component input. 

- **template:** The template used to format an individual request.
