### ⛓️LangFlow example:

![Description](img/llm-chain.png#only-dark)
![Description](img/llm-chain.png#only-light)

[Get JSON file](data/llm-chain.json){: .md-button download="llm-chain"} 

## Nodes

The `PromptTemplate` is a simple template that takes in a product name and returns a prompt. The prompt is used to generate the response from the LLM.

Template:
    
``` txt
I want you to act as a naming consultant for new companies.

Here are some examples of good company names:

- search engine, Google
- social media, Facebook
- video sharing, YouTube

The name should be short, catchy, and easy to remember.

What is a good name for a company that makes {product}?
```

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=_blank} requires you to create an account to get your API key.

Check the short tutorial of [OpenAI](llms.md){.internal-link target=_blank} options available.

The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input, and returns the response from an LLM.