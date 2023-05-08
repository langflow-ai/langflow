`VectorStoreRouterAgent` construct an agent that routes between vector stores.

![Description](img/single_node/mult_vect.png#only-light){width=60%}
![Description](img/single_node/mult_vect2.png#only-dark){width=60%}

For more information about [VectorStoreRouterAgent](https://python.langchain.com/en/latest/modules/agents/agent_executors/examples/agent_vectorstore.html?highlight=Router){.internal-link target=_blank}, check out the LangChain documentation.

### ⛓️LangFlow example
![Description](img/multiple-vectorstores.png#only-dark){width=80%}
![Description](img/multiple-vectorstores.png#only-light){width=80%}

[Get JSON file](data/Multiple_vectorstores.json){: .md-button download="Multiple_vectorstores"} 

`TextLoader` loads text from a file.

File used:
[Get txt file](data/state_of_the_union.txt){: state-of-the-union}

By using `WebBaseLoader`, you can load all text from webpages into a document format that we can use downstream. Web path used:
``` txt
https://beta.ruff.rs/docs/faq/
```

`CharacterTextSplitter` implements splitting text based on characters. 

Text splitters operate as follows:

- Split the text into small, meaningful chunks (usually sentences).

- Combine these small chunks into larger ones until they reach a certain size (measured by a function).

- Once a chunk reaches the desired size, make it its piece of text and create a new chunk with some overlap to maintain context.

Separator used:
``` txt
.
```
Chunk size used:
``` txt
4000
```
Chunk overlap used:
``` txt
200
```

The `OpenAIEmbeddings`, wrapper around [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings/what-are-embeddings){.internal-link target=_blank} models. Make sure to get the API key from the LLM provider, in this case [OpenAI](https://platform.openai.com/){.internal-link target=_blank}.

`Chroma` vector databases can be used as vector stores to conduct a semantic search or to select examples, thanks to a wrapper around them.

A `VectorStoreInfo` set information about the vector store, such as the name and description.

**First VectorStoreInfo**

Name:
``` txt
state_of_union_address
```
Description:
``` txt
the most recent state of the Union address
```
**Second VectorStoreInfo**

Name:
``` txt
ruff
```
Description:
``` txt
Information about the Ruff python linting library
```
The `VectorStoreRouterToolkit` is a toolkit that allows you to create a `VectorStoreRouter` agent. This allows it to route between vector stores.

For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=_blank} requires you to create an account to get your API key.

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=_blank} documentation to learn more about the API and the options that contain in the node.