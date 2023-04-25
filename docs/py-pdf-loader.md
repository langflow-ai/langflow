## Nodes

With `PyPDFLoader`, you can load a PDF file with pypdf and chunks at a character level.

File path: [Get PDF file](data/example.pdf){.internal-link target=_blank}

`CharacterTextSplitter` implementation of splitting text that looks at characters. Dealing with long pieces of text requires splitting them into smaller chunks, which can be a complex task. It is important to keep semantically related pieces of text together, though what constitutes semantic relatedness can vary depending on the text.
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
1000
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
example
```
Description used:
``` txt
USENIX Example Paper
```

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/account/api-keys){.internal-link target=_blank} requires you to create an account to get your API key.

Check the short tutorial of [OpenAI](llms.md){.internal-link target=_blank} options available.



The `VectoStoreAgent`is an agent designed to retrieve information from one or more vector stores, either with or without sources.

### ⛓️LangFlow

![!Description](img/py-pdf-loader.png#only-dark)
![!Description](img/py-pdf-loader.png#only-light)

[Get JSON file](data/Py-pdf-loader.json){: py-pdf-loader}