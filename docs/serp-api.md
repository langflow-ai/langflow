### ⛓️LangFlow

![Description](img/serp-api.png#only-dark)
![Description](img/serp-api.png#only-light)

[Get JSON file](data/Serp-api.json){.internal-link target=_blank}

## Nodes

`ZeroShotPrompt` is a tool that allows you to create a prompt template for Zero-Shot Agent. You can set the *Prefix* and *Suffix*. The *Prefix* is the text that will be added before the input text. The *Suffix* is the text that will be added after the input text. In the example, we used the *default* that is automatically set.

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/account/api-keys){.internal-link target=_blank} requires you to create an account to get your API key.

Check the short tutorial of [OpenAI](llms.md){.internal-link target=_blank} options available.

The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input, and returns the response from an LLM.

`Search` is a search engine. Useful to answer questions about current events. To use the Serp API, you first need to sign up [Serp API](https://serpapi.com/){.internal-link target=_blank} for an API key on the provider's website.

The Serp API (Search Engine Results Page API) is an API (Application Programming Interface) that allows developers to scrape search engine results from various search engines such as Google, Bing, Yahoo, and more.

`ZeroShotAgent` is an agent Agent for the MRKL chain. It uses a Zero Shot LLM to generate a response.