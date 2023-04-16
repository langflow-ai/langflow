The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input and returns the response from an LLM.

![!Description](img/llm-chain.png#only-dark)
![!Description](img/llm-chain.png#only-light)

[Get json file](data/llm-chain.json){: llm-chain}

Template:
    
``` txt
I want you to act as a naming consultant for new companies.

Here are some examples of good company names:

- search engine, Google
- social media, Facebook
- video sharing, YouTube

The name should be short, catchy and easy to remember.

What is a good name for a company that makes {product}?
```