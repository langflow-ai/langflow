### ⛓️LangFlow

![Description](img/vectorstore-agent.png#only-dark)
![Description](img/vectorstore-agent.png#only-light)

[Get JSON file](data/Vectorstore-agent.json){: .md-button download="Vectorstore-agent"} 

## Nodes

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

The `OpenAIEmbeddings`, wrapper around [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings/what-are-embeddings){.internal-link target=_blank} models. Make sure to get the API key from the LLM provider, in this case [OpenAI](https://platform.openai.com/account/api-keys){.internal-link target=_blank}.

`Chroma` vector databases can be used as vector stores to conduct a semantic search or to select examples, thanks to a wrapper around them.

A `VectorStoreInfo` set information about the vector store, such as the name and description.

Name used:
``` txt
ruff
```
Description used:
``` txt
Information about the Ruff python linting library
```

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/account/api-keys){.internal-link target=_blank} requires you to create an account to get it yours.

Check the short tutorial of [OpenAI](llms.md){.internal-link target=_blank} options available.



The `VectoStoreAgent`is an agent designed to retrieve information from one or more vector stores, either with or without sources.
