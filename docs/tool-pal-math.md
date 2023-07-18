`PAL-MATH` is a language model that is good at solving complex math problems. The input should be a fully worded hard-word math problem.

<br>

![Description](img/single_node/pal_math.png#only-light){width=50%}
![Description](img/single_node/pal_math2.png#only-dark){width=50%}

To understand more, check out the LangChain [PAL-MATH](https://python.langchain.com/en/latest/modules/chains/examples/pal.html?highlight=PAL-MATH){.internal-link target=\_blank} documentation.

---

### ⛓️LangFlow example

![Description](img/tool-pal-math2.png#only-dark){width=100%}
![Description](img/tool-pal-math.png#only-light){width=100%}

<br>

[Download Flow](data/Tool_pal_math.json){: .md-button download="Tool_pal_math"}

<br>

`ZeroShotPrompt` creates a prompt template for Zero-Shot Agent. You can set the _Prefix_ and _Suffix_. The _Prefix_ is the text that will be added before the input text. The _Suffix_ is the text that will be added after the input text. In the example, we used the _default_ that is automatically set.

<br>

For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=\_blank} requires you to create an account to get your API key.

<br>

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=\_blank} documentation to learn more about the API and the options that contain in the node.

<br>

The `LLMChain` is a simple chain that takes in a prompt template, formats it with the user input, and returns the response from an LLM.

<br>

`ZeroShotAgent` is an agent Agent for the MRKL chain. It uses a Zero Shot LLM to generate a response.
