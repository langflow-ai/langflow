The `JsonAgent` is an agent designed to interact with large JSON/dict objects.

<br>

![Description](img/single_node/json_ag.png#only-light){width=50%}
![Description](img/single_node/json_ag2.png#only-dark){width=50%}

<br>

To understand more, check out the LangChain [JsonAgent](https://python.langchain.com/en/latest/modules/agents/toolkits/examples/json.html){.internal-link target=\_blank} documentation.

---

### ⛓️LangFlow example

![Description](img/json-agent2.png#only-dark){width=100%}
![Description](img/json-agent.png#only-light){width=100%}

<br>

[Download Flow](data/Json_agent.json){: .md-button download="Json_agent"}

<br>

`JsonSpec` will define the **Max value length** of the input and output of the agent. You can get the **Path** file [here](https://raw.githubusercontent.com/openai/openai-openapi/master/openapi.yaml){.internal-link target=\_blank}.

<br>

**Max value length**:

```txt
400
```

For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=\_blank} requires you to create an account to get your API key.

<br>

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=\_blank} documentation to learn more about the API and the options that contain in the node.

<br>

`JsonToolkit` for interacting with the JSON spec.
