---
title: Language models
slug: /components-models
---

import Icon from "@site/src/components/icon";

:::important
In [Langflow version 1.5](/release-notes), the singular **Language model** component replaces many provider-specific model components. Any provider-specific model components that weren't incorporated into the singular component were moved to [Bundles](/components-bundle-components).
:::

Language components in Langflow generate text using the selected Large Language Model (LLM). The core **Language model** component supports many LLM providers, models, and use cases. For additional providers and models not supported by the core **Language model** component, see [**Bundles**](/components-bundle-components).

Most use cases can be performed with the **Language Model** and **Embedding Model** components.

If you want to try additional providers not supported by the new components, the single-provider LLM components of both the **Language Model** and **Embedding Model** types are now found in **Bundles**, and are still available for use.

### Use a Language Model component in a flow

Use a **Language Model** component in your flow anywhere you would use an LLM.

Model components receive inputs and prompts for generating text, and the generated text is sent to an output component.

This example has the OpenAI model in a chatbot flow. For more information, see the [Basic prompting flow](/basic-prompting).

1. Add the **Language Model** component to your flow.
The default model is OpenAI's GPT-4.1 mini model. Based on [OpenAI's recommendations](https://platform.openai.com/docs/models/gpt-4.1-mini), this model is a good, balanced starter model.
2. In the **OpenAI API Key** field, enter your OpenAI API key.
3. Add a [Prompt](/components-prompts) component to your flow.
4. To connect the [Prompt](/components-prompts) component to the **Language Model** component, on the **Language Model** component, click **Controls**.
5. Enable the **System Message** setting.
On the **Language Model** component, a new **System Message** port opens.
6. Connect the **Prompt** port to the **System Message** port.
7. Add [Chat input](/components-io#chat-input) and [Chat output](/components-io#chat-output) components to your flow.
Your flow looks like this:
![A Language Model component for basic prompting](/img/component-language-model.png)

8. Open the **Playground**, and ask a question.
The bot responds to your question with sources.

    ```
    What is the capital of Utah?

    AI
    gpt-4o-mini
    The capital of Utah is Salt Lake City. It is not only the largest city in the state but also serves as the cultural and economic center of Utah. Salt Lake City was founded in 1847 by Mormon pioneers and is known for its proximity to the Great Salt Lake and its role in the history of the Church of Jesus Christ of Latter-day Saints. For more information, you can refer to sources such as the U.S. Geological Survey or the official state website of Utah.
    ```

9. Try an alternate model provider, and test how the response differs.
In the **Language Model** component, in the **Model Provider** field, select **Anthropic**.
10. In the **Model Name** field, select your Anthropic model.
This model uses Claude 3.5 Haiku, based on [Anthropic's recommendation](https://docs.anthropic.com/en/docs/about-claude/models/choosing-a-model) for a fast and cost-effective model.
11. In the **Anthropic API Key** field, enter your Anthropic API key.
12. Open the **Playground**, and ask the same question as you did before.

    ```
    User
    What is the capital of Utah?

    AI
    claude-3-5-haiku-latest
    The capital of Utah is Salt Lake City. It is also the most populous city in the state. Salt Lake City has been the capital of Utah since 1896, when Utah became a state.
    Sources:
    Utah State Government Official Website (utah.gov)
    U.S. Census Bureau
    Encyclopedia Britannica
    ```

The response from the Anthropic model is less verbose, and lists its sources outside of the informative paragraph.
For more information, see your LLM provider's documentation.

### Use the LanguageModel output

The default output of the language model is the model's response as a `Message`, but it also supports a `LanguageModel` output.
Select the Language Model's **LanguageModel** output to connect it to components that require an LLM.

For an example, see the [Smart function component](/components-processing#smart-function), which requires an LLM connected through this port to create a function from your natural language.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| provider | String | The model provider to use. |
| model_name | String | The name of the model to use. Options depend on the selected provider. |
| api_key | SecretString | The API Key for authentication with the selected provider. |
| input_value | String | The input text to send to the model. |
| system_message | String | A system message that helps set the behavior of the assistant. |
| stream | Boolean | Whether to stream the response. Default: `False`. |
| temperature | Float | Controls randomness in responses. Range: `[0.0, 1.0]`. Default: `0.1`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of Chat configured with the specified parameters. |

</details>

## Language models bundles

If your provider or model isn't supported by the core **Language model** component, see [Bundles](/components-bundle-components) for additional language model and embedding model components developed by third-party contributors.