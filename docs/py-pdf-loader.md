With `PyPDFLoader`, you can load a PDF file with pypdf and chunks at a character level.

<br>

![Description](img/single_node/pypdf.png#only-light){width=50%}
![Description](img/single_node/pypdf2.png#only-dark){width=50%}

<br>

You can check more about the [PyPDFLoader](https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/pdf.html?highlight=PDF){.internal-link target=\_blank} in the LangChain documentation.

---

### ⛓️LangFlow example

![Description](img/py-pdf-loader2.png#only-dark){width=100%}
![Description](img/py-pdf-loader.png#only-light){width=100%}

<br>

[Download Flow](data/Py_pdf_loader.json){: .md-button download="Py_pdf_loader"}

<br>

`File path:`

<br>

[Download PDF](data/example.pdf){: .md-button download="example.pdf"}

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

The `OpenAIEmbeddings`, wrapper around [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings/what-are-embeddings){.internal-link target=\_blank} models. Make sure to get the API key from the LLM provider, in this case [OpenAI](https://platform.openai.com/){.internal-link target=\_blank}.

<br>

`Chroma` vector databases can be used as vector stores to conduct a semantic search or to select examples, thanks to a wrapper around them.

<br>

A `VectorStoreInfo` set information about the vector store, such as the name and description.

<br>

**Name used**:

```txt
example
```

**Description used**:

```txt
USENIX Example Paper.
```

<br>

For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=\_blank} requires you to create an account to get your API key.

<br>

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=\_blank} documentation to learn more about the API and the options that contain in the node.

<br>

The `VectoStoreAgent`is an agent designed to retrieve information from one or more vector stores, either with or without sources.
