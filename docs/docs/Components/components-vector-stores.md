---
title: Vector Stores
sidebar_position: 7
slug: /components-vector-stores
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




### Astra DB {#453bcf5664154e37a920f1b602bd39da}


The `Astra DB` initializes a vector store using Astra DB from Data. It creates Astra DB-based vector indexes to efficiently store and retrieve documents.


**Parameters:**

- **Input:** Documents or Data for input.
- **Embedding or Astra vectorize:** External or server-side model Astra DB uses.
- **Collection Name:** Name of the Astra DB collection.
- **Token:** Authentication token for Astra DB.
- **API Endpoint:** API endpoint for Astra DB.
- **Namespace:** Astra DB namespace.
- **Metric:** Metric used by Astra DB.
- **Batch Size:** Batch size for operations.
- **Bulk Insert Batch Concurrency:** Concurrency level for bulk inserts.
- **Bulk Insert Overwrite Concurrency:** Concurrency level for overwriting during bulk inserts.
- **Bulk Delete Concurrency:** Concurrency level for bulk deletions.
- **Setup Mode:** Setup mode for the vector store.
- **Pre Delete Collection:** Option to delete the collection before setup.
- **Metadata Indexing Include:** Fields to include in metadata indexing.
- **Metadata Indexing Exclude:** Fields to exclude from metadata indexing.
- **Collection Indexing Policy:** Indexing policy for the collection.

NOTE


Ensure you configure the necessary Astra DB token and API endpoint before starting.


---


### Astra DB Search {#26f25d1933a9459bad2d6725f87beb11}


`Astra DBSearch` searches an existing Astra DB vector store for documents similar to the input. It uses the `Astra DB`component's functionality for efficient retrieval.


**Parameters:**

- **Search Type:** Type of search, such as Similarity or MMR.
- **Input Value:** Value to search for.
- **Embedding or Astra vectorize:** External or server-side model Astra DB uses.
- **Collection Name:** Name of the Astra DB collection.
- **Token:** Authentication token for Astra DB.
- **API Endpoint:** API endpoint for Astra DB.
- **Namespace:** Astra DB namespace.
- **Metric:** Metric used by Astra DB.
- **Batch Size:** Batch size for operations.
- **Bulk Insert Batch Concurrency:** Concurrency level for bulk inserts.
- **Bulk Insert Overwrite Concurrency:** Concurrency level for overwriting during bulk inserts.
- **Bulk Delete Concurrency:** Concurrency level for bulk deletions.
- **Setup Mode:** Setup mode for the vector store.
- **Pre Delete Collection:** Option to delete the collection before setup.
- **Metadata Indexing Include:** Fields to include in metadata indexing.
- **Metadata Indexing Exclude:** Fields to exclude from metadata indexing.
- **Collection Indexing Policy:** Indexing policy for the collection.

---


### Chroma {#74730795605143cba53e1f4c4f2ef5d6}


`Chroma` sets up a vector store using Chroma for efficient vector storage and retrieval within language processing workflows.


**Parameters:**

- **Collection Name:** Name of the collection.
- **Persist Directory:** Directory to persist the Vector Store.
- **Server CORS Allow Origins (Optional):** CORS allow origins for the Chroma server.
- **Server Host (Optional):** Host for the Chroma server.
- **Server Port (Optional):** Port for the Chroma server.
- **Server gRPC Port (Optional):** gRPC port for the Chroma server.
- **Server SSL Enabled (Optional):** SSL configuration for the Chroma server.
- **Input:** Input data for creating the Vector Store.
- **Embedding:** Embeddings used for the Vector Store.

For detailed documentation and integration guides, please refer to the [Chroma Component Documentation](https://python.langchain.com/docs/integrations/vectorstores/chroma).


---


### Chroma Search {#5718072a155441f3a443b944ad4d638f}


`ChromaSearch` searches a Chroma collection for documents similar to the input text. It leverages Chroma to ensure efficient document retrieval.


**Parameters:**

- **Input:** Input text for search.
- **Search Type:** Type of search, such as Similarity or MMR.
- **Collection Name:** Name of the Chroma collection.
- **Index Directory:** Directory where the Chroma index is stored.
- **Embedding:** Embedding model used for vectorization.
- **Server CORS Allow Origins (Optional):** CORS allow origins for the Chroma server.
- **Server Host (Optional):** Host for the Chroma server.
- **Server Port (Optional):** Port for the Chroma server.
- **Server gRPC Port (Optional):** gRPC port for the Chroma server.
- **Server SSL Enabled (Optional):** SSL configuration for the Chroma server.

---


### Couchbase {#6900a79347164f35af27ae27f0d64a6d}


`Couchbase` builds a Couchbase vector store from Data, streamlining the storage and retrieval of documents.


**Parameters:**

- **Embedding:** Model used by Couchbase.
- **Input:** Documents or Data.
- **Couchbase Cluster Connection String:** Cluster Connection string.
- **Couchbase Cluster Username:** Cluster Username.
- **Couchbase Cluster Password:** Cluster Password.
- **Bucket Name:** Bucket identifier in Couchbase.
- **Scope Name:** Scope identifier in Couchbase.
- **Collection Name:** Collection identifier in Couchbase.
- **Index Name:** Index identifier.

For detailed documentation and integration guides, please refer to the [Couchbase Component Documentation](https://python.langchain.com/docs/integrations/vectorstores/couchbase).


---


### Couchbase Search {#c77bb09425a3426f9677d38d8237d9ba}


`CouchbaseSearch` leverages the Couchbase component to search for documents based on similarity metric.


**Parameters:**

- **Input:** Search query.
- **Embedding:** Model used in the Vector Store.
- **Couchbase Cluster Connection String:** Cluster Connection string.
- **Couchbase Cluster Username:** Cluster Username.
- **Couchbase Cluster Password:** Cluster Password.
- **Bucket Name:** Bucket identifier.
- **Scope Name:** Scope identifier.
- **Collection Name:** Collection identifier in Couchbase.
- **Index Name:** Index identifier.

---


### FAISS {#5b3f4e6592a847b69e07df2f674a03f0}


The `FAISS` component manages document ingestion into a FAISS Vector Store, optimizing document indexing and retrieval.


**Parameters:**

- **Embedding:** Model used for vectorizing inputs.
- **Input:** Documents to ingest.
- **Folder Path:** Save path for the FAISS index, relative to Langflow.

For more details, see the [FAISS Component Documentation](https://faiss.ai/index.html).


---


### FAISS Search {#81ff12d7205940a3b14e3ddf304630f8}


`FAISSSearch` searches a FAISS Vector Store for documents similar to a given input, using similarity metrics for efficient retrieval.


**Parameters:**

- **Embedding:** Model used in the FAISS Vector Store.
- **Folder Path:** Path to load the FAISS index from, relative to Langflow.
- **Input:** Search query.
- **Index Name:** Index identifier.

---


### MongoDB Atlas {#eba8892f7a204b97ad1c353e82948149}


`MongoDBAtlas` builds a MongoDB Atlas-based vector store from Data, streamlining the storage and retrieval of documents.


**Parameters:**

- **Embedding:** Model used by MongoDB Atlas.
- **Input:** Documents or Data.
- **Collection Name:** Collection identifier in MongoDB Atlas.
- **Database Name:** Database identifier.
- **Index Name:** Index identifier.
- **MongoDB Atlas Cluster URI:** Cluster URI.
- **Search Kwargs:** Additional search parameters.

NOTE


Ensure pymongo is installed for using MongoDB Atlas Vector Store.


---


### MongoDB Atlas Search {#686ba0e30a54438cbc7153b81ee4b1df}


`MongoDBAtlasSearch` leverages the MongoDBAtlas component to search for documents based on similarity metrics.


**Parameters:**

- **Search Type:** Type of search, such as "Similarity" or "MMR".
- **Input:** Search query.
- **Embedding:** Model used in the Vector Store.
- **Collection Name:** Collection identifier.
- **Database Name:** Database identifier.
- **Index Name:** Index identifier.
- **MongoDB Atlas Cluster URI:** Cluster URI.
- **Search Kwargs:** Additional search parameters.

---


### PGVector {#7ceebdd84ab14f8e8589c13c58370e5b}


`PGVector` integrates a Vector Store within a PostgreSQL database, allowing efficient storage and retrieval of vectors.


**Parameters:**

- **Input:** Value for the Vector Store.
- **Embedding:** Model used.
- **PostgreSQL Server Connection String:** Server URL.
- **Table:** Table name in the PostgreSQL database.

For more details, see the [PGVector Component Documentation](https://python.langchain.com/docs/integrations/vectorstores/pgvector).


NOTE


Ensure the PostgreSQL server is accessible and configured correctly.


---


### PGVector Search {#196bf22ea2844bdbba971b5082750943}


`PGVectorSearch` extends `PGVector` to search for documents based on similarity metrics.


**Parameters:**

- **Input:** Search query.
- **Embedding:** Model used.
- **PostgreSQL Server Connection String:** Server URL.
- **Table:** Table name.
- **Search Type:** Type of search, such as "Similarity" or "MMR".

---


### Pinecone {#67abbe3e27c34fb4bcb35926ce831727}


`Pinecone` constructs a Pinecone wrapper from Data, setting up Pinecone-based vector indexes for document storage and retrieval.


**Parameters:**

- **Input:** Documents or Data.
- **Embedding:** Model used.
- **Index Name:** Index identifier.
- **Namespace:** Namespace used.
- **Pinecone API Key:** API key.
- **Pinecone Environment:** Environment settings.
- **Search Kwargs:** Additional search parameters.
- **Pool Threads:** Number of threads.

:::info

Ensure the Pinecone API key and environment are correctly configured.

:::




---


### Pinecone Search {#977944558cad4cf2ba332ea4f06bf485}


`PineconeSearch` searches a Pinecone Vector Store for documents similar to the input, using advanced similarity metrics.


**Parameters:**

- **Search Type:** Type of search, such as "Similarity" or "MMR".
- **Input Value:** Search query.
- **Embedding:** Model used.
- **Index Name:** Index identifier.
- **Namespace:** Namespace used.
- **Pinecone API Key:** API key.
- **Pinecone Environment:** Environment settings.
- **Search Kwargs:** Additional search parameters.
- **Pool Threads:** Number of threads.

---


### Qdrant {#88df77f3044e4ac6980950835a919fb0}


`Qdrant` allows efficient similarity searches and retrieval operations, using a list of texts to construct a Qdrant wrapper.


**Parameters:**

- **Input:** Documents or Data.
- **Embedding:** Model used.
- **API Key:** Qdrant API key.
- **Collection Name:** Collection identifier.
- **Advanced Settings:** Includes content payload key, distance function, gRPC port, host, HTTPS, location, metadata payload key, path, port, prefer gRPC, prefix, search kwargs, timeout, URL.

---


### Qdrant Search {#5ba5f8dca0f249d7ad00778f49901e6c}


`QdrantSearch` extends `Qdrant` to search for documents similar to the input based on advanced similarity metrics.


**Parameters:**

- **Search Type:** Type of search, such as "Similarity" or "MMR".
- **Input Value:** Search query.
- **Embedding:** Model used.
- **API Key:** Qdrant API key.
- **Collection Name:** Collection identifier.
- **Advanced Settings:** Includes content payload key, distance function, gRPC port, host, HTTPS, location, metadata payload key, path, port, prefer gRPC, prefix, search kwargs, timeout, URL.

---


### Redis {#a0fb8a9d244a40eb8439d0f8c22a2562}


`Redis` manages a Vector Store in a Redis database, supporting efficient vector storage and retrieval.


**Parameters:**

- **Index Name:** Default index name.
- **Input:** Data for building the Redis Vector Store.
- **Embedding:** Model used.
- **Schema:** Optional schema file (.yaml) for document structure.
- **Redis Server Connection String:** Server URL.
- **Redis Index:** Optional index name.

For detailed documentation, refer to the [Redis Documentation](https://python.langchain.com/docs/integrations/vectorstores/redis).


:::info

Ensure the Redis server URL and index name are configured correctly. Provide a schema if no documents are available.

:::




---


### Redis Search {#80aea4da515f490e979c8576099ee880}


`RedisSearch` searches a Redis Vector Store for documents similar to the input.


**Parameters:**

- **Search Type:** Type of search, such as "Similarity" or "MMR".
- **Input Value:** Search query.
- **Index Name:** Default index name.
- **Embedding:** Model used.
- **Schema:** Optional schema file (.yaml) for document structure.
- **Redis Server Connection String:** Server URL.
- **Redis Index:** Optional index name.

---


### Supabase {#e86fb3cc507e4b5494f0a421f94e853b}


`Supabase` initializes a Supabase Vector Store from texts and embeddings, setting up an environment for efficient document retrieval.


**Parameters:**

- **Input:** Documents or data.
- **Embedding:** Model used.
- **Query Name:** Optional query name.
- **Search Kwargs:** Advanced search parameters.
- **Supabase Service Key:** Service key.
- **Supabase URL:** Instance URL.
- **Table Name:** Optional table name.

:::info

Ensure the Supabase service key, URL, and table name are properly configured.

:::




---


### Supabase Search {#fd02d550b9b2457f91f2f4073656cb09}


`SupabaseSearch` searches a Supabase Vector Store for documents similar to the input.


**Parameters:**

- **Search Type:** Type of search, such as "Similarity" or "MMR".
- **Input Value:** Search query.
- **Embedding:** Model used.
- **Query Name:** Optional query name.
- **Search Kwargs:** Advanced search parameters.
- **Supabase Service Key:** Service key.
- **Supabase URL:** Instance URL.
- **Table Name:** Optional table name.

---


### Vectara {#b4e05230b62a47c792a89c5511af97ac}


`Vectara` sets up a Vectara Vector Store from files or upserted data, optimizing document retrieval.


**Parameters:**

- **Vectara Customer ID:** Customer ID.
- **Vectara Corpus ID:** Corpus ID.
- **Vectara API Key:** API key.
- **Files Url:** Optional URLs for file initialization.
- **Input:** Optional data for corpus upsert.

For more information, consult the [Vectara Component Documentation](https://python.langchain.com/docs/integrations/vectorstores/vectara).


:::info

If inputs or files_url are provided, they will be processed accordingly.

:::




---


### Vectara Search {#31a47221c23f4fbba4a7465cf1d89eb0}


`VectaraSearch` searches a Vectara Vector Store for documents based on the provided input.


**Parameters:**

- **Search Type:** Type of search, such as "Similarity" or "MMR".
- **Input Value:** Search query.
- **Vectara Customer ID:** Customer ID.
- **Vectara Corpus ID:** Corpus ID.
- **Vectara API Key:** API key.
- **Files Url:** Optional URLs for file initialization.

---


### Weaviate {#57c7969574b1418dbb079ac5fc8cd857}


`Weaviate` facilitates a Weaviate Vector Store setup, optimizing text and document indexing and retrieval.


**Parameters:**

- **Weaviate URL:** Default instance URL.
- **Search By Text:** Indicates whether to search by text.
- **API Key:** Optional API key for authentication.
- **Index Name:** Optional index name.
- **Text Key:** Default text extraction key.
- **Input:** Document or record.
- **Embedding:** Model used.
- **Attributes:** Optional additional attributes.

For more details, see the [Weaviate Component Documentation](https://python.langchain.com/docs/integrations/vectorstores/weaviate).


NOTE


Ensure Weaviate instance is running and accessible. Verify API key, index name, text key, and attributes are set correctly.


---


### Weaviate Search {#6d4e616dfd6143b28dc055bc1c40ecae}


`WeaviateSearch` searches a Weaviate Vector Store for documents similar to the input.


**Parameters:**

- **Search Type:** Type of search, such as "Similarity" or "MMR".
- **Input Value:** Search query.
- **Weaviate URL:** Default instance URL.
- **Search By Text:** Indicates whether to search by text.
- **API Key:** Optional API key for authentication.
- **Index Name:** Optional index name.
- **Text Key:** Default text extraction key.
- **Embedding:** Model used.
- **Attributes:** Optional additional attributes.
