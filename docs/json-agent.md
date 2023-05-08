The `JsonAgent` is an agent designed to interact with large JSON/dict objects.

![Description](img/single_node/json_ag.png#only-light){width=60%}
![Description](img/single_node/json_ag2.png#only-dark){width=60%}

To understand more, check out the LangChain [JsonAgent](https://python.langchain.com/en/latest/modules/agents/toolkits/examples/json.html){.internal-link target=_blank} documentation.
### ⛓️LangFlow example
![Description](img/json-agent.png#only-dark){width=80%}
![Description](img/json-agent.png#only-light){width=80%}

[Get JSON file](data/Json_agent.json){: .md-button download="Json_agent"}

`JsonSpec` will define the **Max value length** of the input and output of the agent. You can get the **Path**  file [here](https://github.com/openai/openai-openapi/blob/master/openapi.yaml){.internal-link target=_blank}.

Max value length:
``` txt
400
```
For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=_blank} requires you to create an account to get your API key.

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=_blank} documentation to learn more about the API and the options that contain in the node.

`JsonToolkit` for interacting with the JSON spec.