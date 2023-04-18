## Nodes used:

`ZeroShotPrompt` is a tool that allows you to create a prompt template for Zero Shot Agent. You can set the *Prefix* and *Suffix*. The *Prefix* is the text that will be added before the input text. The *Suffix* is the text that will be added after the input text. In the example, we used the *default* that is automatically set.

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/account/api-keys){.internal-link target=_blank} requires you to create an account to get your API key.

Check the short tutorial of [OpenAI inputs](llms.md){.internal-link target=_blank} available.

The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input and returns the response from an LLM.

`PAL-MATH`, a language model that is really good at solving complex math problems. The inpult should be a fully worded hard word math problem.

`ZeroShotAgent` is an agent Agent for the MRKL chain. It uses a Zero Shot LLM to generate a response.

### ⛓️LangFlow example:

![!Description](img/tool-pal-math.png#only-dark)
![!Description](img/tool-pal-math.png#only-light)

[Get json file](data/Tool-pal-math.json){: pal-math}