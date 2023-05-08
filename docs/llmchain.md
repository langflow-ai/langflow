The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input, and returns the response from an LLM.

![Description](img/single_node/guideline2.png#only-dark){width=60%}
![Description](img/single_node/guideline.png#only-light){width=60%}

More information about the [LLMChain](https://python.langchain.com/en/latest/modules/chains/generic/llm_chain.html){.internal-link target=_blank} can be found in the LangChain documentation.

### ⛓️LangFlow example

![Description](img/llm-chain.png#only-dark){width=80%}
![Description](img/llm-chain.png#only-light){width=80%}

[Get JSON file](data/llm_chain.json){: .md-button download="llm_chain"} 


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

For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=_blank} requires you to create an account to get your API key.

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=_blank} documentation to learn more about the API and the options that contain in the node.