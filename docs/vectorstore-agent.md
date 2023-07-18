The `VectoStoreAgent`is an agent designed to retrieve information from one or more vectorstores, either with or without sources.

<br>

![Description](img/single_node/vec_sto_agt.png#only-light){width=50%}
![Description](img/single_node/vec_sto_agt2.png#only-dark){width=50%}

<br>

Check out the [VectoStoreAgent](https://python.langchain.com/en/latest/modules/agents/toolkits/examples/vectorstore.html){.internal-link target=\_blank} in the LangChain documentation.

---

### ⛓️LangFlow example

![Description](img/vectorstore-agent2.png#only-dark){width=100%}
![Description](img/vectorstore-agent.png#only-light){width=100%}

<br>

[Download Flow](data/Vectorstore_agent.json){: .md-button download="Vectorstore_agent"}

<br>

By using `WebBaseLoader`, you can load all text from webpages into a document format that we can use downstream. Web path used:

```txt
https://beta.ruff.rs/docs/faq/
```

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

`Chroma` vector databases can be used as vectorstores to conduct a semantic search or to select examples, thanks to a wrapper around them.

<br>

A `VectorStoreInfo` set information about the vectorstore, such as the name and description.

Name used:

```txt
ruff
```

Description used:

```txt
Information about the Ruff python linting library
```

<br>

For the example, we used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/){.internal-link target=\_blank} requires you to create an account to get your API key.

<br>

Check out the [OpenAI](https://platform.openai.com/docs/introduction/overview){.internal-link target=\_blank} documentation to learn more about the API and the options that contain in the node.
