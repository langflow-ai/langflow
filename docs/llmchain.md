The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input and returns the response from an LLM.

To use the `LLMChain`, first create a prompt template.

Template:
    
``` txt
"Write a catchphrase for the following company: {company_name}"
```

The we can create a very simple chain that will take user input, format the prompt with it, and then send it to the LLM.

![!Description](img/llm.png#only-dark)
![!Description](img/llm.png#only-light)

[Get json file](data/Llm-chain.json){: llm-chain}