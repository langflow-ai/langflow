### ⛓️LangFlow example:

![Description](img/csv-loader.png#only-dark)
![Description](img/csv-loader.png#only-light)

[Get JSON file](data/Csv-loader.json){: .md-button download="Csv-loader"} 

## Nodes

The `CSVLoader` loads a CSV file into a list of documents.

File path: [Get CSV file](data/organizations-100.csv){.internal-link target=_blank}


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

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=_blank} requires you to create an account to get your API key.

Check the short tutorial of [OpenAI](llms.md){.internal-link target=_blank} options available.

The `OpenAIEmbeddings`, wrapper around [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings/what-are-embeddings){.internal-link target=_blank} models. Make sure to get the API key from the LLM provider, in this case [OpenAI](https://platform.openai.com/){.internal-link target=_blank}.

`Chroma` vector databases can be used as vector stores to conduct a semantic search or to select examples, thanks to a wrapper around them.

A `VectorStoreInfo` set information about the vector store, such as the name and description.

Name used:
``` txt
organizations-100
```
Description used:
``` txt
A table contains 100 companies.
```

The `VectoStoreAgent`is an agent designed to retrieve information from one or more vector stores, either with or without sources.