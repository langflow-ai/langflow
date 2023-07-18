The `CSVLoader` loads a CSV file into a list of documents.

<br>

![Description](img/single_node/csv_loader.png#only-light){width=50%}
![Description](img/single_node/csv_loader2.png#only-dark){width=50%}

<br>

Check out more about the `CSVLoader` in [LangChain](https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/csv.html?highlight=CSV%20loader){.internal-link target=\_blank} documentation.

---

### ⛓️LangFlow example

![Description](img/csv-loader2.png#only-dark){width=100%}
![Description](img/csv-loader.png#only-light){width=100%}

<br>

[Download Flow](data/Csv_loader.json){: .md-button download="Csv_loader"}

<br>

`File path:`

<br>

[Download CSV](data/organizations-100.csv){: .md-button download="organizations-100.csv"}

<br>

`CharacterTextSplitter` implements splitting text based on characters.

Text splitters operate as follows:

- Split the text into small, meaningful chunks (usually sentences).

- Combine these small chunks into larger ones until they reach a certain size (measured by a function).

- Once a chunk reaches the desired size, make it its piece of text and create a new chunk with some overlap to maintain context.

**Separator used**:

```txt
.
```

**Chunk size used**:

```txt
2000
```

**Chunk overlap used**:

```txt
200
```

<br>
For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=_blank} requires you to create an account to get your API key.

<br>

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=\_blank} documentation to learn more about the API and the options that contain in the node.

<br>

The `OpenAIEmbeddings`, wrapper around [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings/what-are-embeddings){.internal-link target=\_blank} models. Make sure to get the API key from the LLM provider, in this case [OpenAI](https://platform.openai.com/){.internal-link target=\_blank}.

<br>

`Chroma` vector databases can be used as vector stores to conduct a semantic search or to select examples, thanks to a wrapper around them.

<br>

A `VectorStoreInfo` set information about the vector store, such as the name and description.

<br>

**Name used**:

```txt
organizations-100
```

**Description used**:

```txt
A table contains 100 companies.
```

The `VectoStoreAgent`is an agent designed to retrieve information from one or more vector stores, either with or without sources.
