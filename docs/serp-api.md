`Search` is a search engine useful to answer questions about current events. To use the Serp API, you first need to sign up [Serp API](https://serpapi.com/){.internal-link target=_blank} for an API key on the provider's website.

The Serp API (Search Engine Results Page API) is an API (Application Programming Interface) that allows developers to scrape search engine results from various search engines such as Google, Bing, Yahoo, and more.

![Description](img/single_node/serp.png#only-light){width=60%}
![Description](img/single_node/serp2.png#only-dark){width=60%}

To understand more, check out the LangChain [Search](https://python.langchain.com/en/latest/modules/agents/tools/examples/google_serper.html){.internal-link target=_blank} documentation.
### ⛓️LangFlow example

![Description](img/serp-api.png#only-dark){width=80%}
![Description](img/serp-api.png#only-light){width=80%}

[Get JSON file](data/Serp_api.json){: .md-button download="Serp_api"} 

`ZeroShotPrompt` creates a prompt template for Zero-Shot Agent. You can set the *Prefix* and *Suffix*. The *Prefix* is the text that will be added before the input text. The *Suffix* is the text that will be added after the input text. In the example, we used the *default* that is automatically set..

For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=_blank} requires you to create an account to get your API key.

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=_blank} documentation to learn more about the API and the options that contain in the node.

The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input, and returns the response from an LLM.

`ZeroShotAgent` is an agent Agent for the MRKL chain. It uses a Zero Shot LLM to generate a response.