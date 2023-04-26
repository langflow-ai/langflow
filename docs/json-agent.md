## Nodes

`JsonSpec` will define the **Max value length** of the input and output of the agent. The **Path** is the path to the JSON file.

Max value length:
``` txt
400
```
We use the OpenAPI spec for OpenAI API in the ⛓️LangFlow example. Get it [here](https://github.com/openai/openai-openapi/blob/master/openapi.yaml){.internal-link target=_blank}.

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/account/api-keys){.internal-link target=_blank} requires you to create an account to get it yours.

Check the short tutorial of [OpenAI](llms.md){.internal-link target=_blank} options available.

`JsonToolkit` for interacting with the JSON spec.

The `JsonAgent` construct an agent that uses a JSON agent from LLM and tools.

### ⛓️LangFlow
![Description](img/json-agent.png#only-dark)
![Description](img/json-agent.png#only-light)

[Get JSON file](data/Json-agent.json){.internal-link target=_blank}