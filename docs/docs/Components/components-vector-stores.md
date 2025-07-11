---
title: Vector stores
slug: /components-vector-stores
---

import Icon from "@site/src/components/icon";

# Vector store components in Langflow

Vector databases store vector data, which backs AI workloads like chatbots and Retrieval Augmented Generation.

Vector database components establish connections to existing vector databases or create in-memory vector stores for storing and retrieving vector data.

Vector database components are distinct from [memory components](/components-memories), which are built specifically for storing and retrieving chat messages from internal Langflow memory or external databases. For more information, see [Memory management options](/memory).

## Use a vector store component in a flow

This example uses the **Chroma DB** vector store component. Your vector store component's parameters and authentication may be different, but the document ingestion workflow is the same. A document is loaded from a local machine and chunked. The vector store component generates embeddings with the connected [model](/components-models) component, and stores them in the connected vector database.

This vector data can then be retrieved for workloads like Retrieval Augmented Generation.

![Embedding data into a vector store](/img/vector-store-document-ingestion.png)

The user's chat input is embedded and compared to the vectors embedded during document ingestion for a similarity search.
The results are output from the vector database component as a [Data](/concepts-objects) object and parsed into text.
This text fills the `{context}` variable in the **Prompt** component, which informs the **Open AI model** component's responses.

![Retrieval from a vector store](/img/vector-store-retrieval.png)

## Astra DB Vector Store

This component implements a Vector Store using Astra DB with search capabilities.

For more information, see the [DataStax documentation](https://docs.datastax.com/en/astra-db-serverless/databases/create-database.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| token | Astra DB Application Token | The authentication token for accessing Astra DB. |
| environment | Environment | The environment for the Astra DB API Endpoint. For example, `dev` or `prod`. |
| database_name | Database | The database name for the Astra DB instance. |
| api_endpoint | Astra DB API Endpoint | The API endpoint for the Astra DB instance. This supersedes the database selection. |
| collection_name | Collection | The name of the collection within Astra DB where the vectors are stored. |
| keyspace | Keyspace | An optional keyspace within Astra DB to use for the collection. |
| embedding_choice | Embedding Model or Astra Vectorize | Choose an embedding model or use Astra vectorize. |
| embedding_model | Embedding Model | Specify the embedding model. Not required for Astra vectorize collections. |
| number_of_results | Number of Search Results | The number of search results to return. Default:`4`. |
| search_type | Search Type | The search type to use. The options are `Similarity`, `Similarity with score threshold`, and `MMR (Max Marginal Relevance)`. |
| search_score_threshold | Search Score Threshold | The minimum similarity score threshold for search results when using the `Similarity with score threshold` option. |
| advanced_search_filter | Search Metadata Filter | An optional dictionary of filters to apply to the search query. |
| autodetect_collection | Autodetect Collection | A boolean flag to determine whether to autodetect the collection. |
| content_field | Content Field | A field to use as the text content field for the vector store. |
| deletion_field | Deletion Based On Field | When provided, documents in the target collection with metadata field values matching the input metadata field value are deleted before new data is loaded. |
| ignore_invalid_documents | Ignore Invalid Documents | A boolean flag to determine whether to ignore invalid documents at runtime. |
| astradb_vectorstore_kwargs | AstraDBVectorStore Parameters | An optional dictionary of additional parameters for the AstraDBVectorStore. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | The Astra DB vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects. |

</details>

### Generate embeddings

The **Astra DB Vector Store** component offers two methods for generating embeddings.

1. **Embedding Model**: Use your own embedding model by connecting an [Embeddings](/components-embedding-models) component in Langflow.

2. **Astra Vectorize**: Use Astra DB's built-in embedding generation service. When creating a new collection, choose the embeddings provider and models, including NVIDIA's `NV-Embed-QA` model hosted by Datastax.

:::important
The embedding model selection is made when creating a new collection and cannot be changed later.
:::

For an example of using the **Astra DB Vector Store** component with an embedding model, see the [Vector Store RAG starter project](/vector-store-rag).

For more information, see the [Astra DB Serverless documentation](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html).

### Hybrid search

The **Astra DB** component includes **hybrid search**, which is enabled by default.

The component fields related to hybrid search are **Search Query**, **Lexical Terms**, and **Reranker**.

* **Search Query** finds results by vector similarity.
* **Lexical Terms** is a comma-separated string of keywords, like `features, data, attributes, characteristics`.
* **Reranker** is the re-ranker model used in the hybrid search.
The re-ranker model is `nvidia/llama-3.2-nv.reranker`.

[Hybrid search](https://docs.datastax.com/en/astra-db-serverless/databases/hybrid-search.html) performs a vector similarity search and a lexical search, compares the results of both searches, and then returns the most relevant results overall.

:::important
To use hybrid search, your collection must be created with vector, lexical, and rerank capabilities enabled. These capabilities are enabled by default when you create a collection in a database in the AWS us-east-2 region.
For more information, see the [DataStax documentation](https://docs.datastax.com/en/astra-db-serverless/api-reference/collection-methods/create-collection.html#example-hybrid).
:::

To use **Hybrid search** in the **Astra DB** component, do the following:

1. Click **New Flow** > **RAG** > **Hybrid Search RAG**.
2. In the **OpenAI** model component, add your **OpenAI API key**.
3. In the **Astra DB** vector store component, add your **Astra DB Application Token**.
4. In the **Database** field, select your database.
5. In the **Collection** field, select or create a collection with hybrid search capabilities enabled.
6. In the **Playground**, enter a question about your data, such as `What are the features of my data?`
Your query is sent to two components: an **OpenAI** model component and the **Astra DB** vector database component.
The **OpenAI** component contains a prompt for creating the lexical query from your input:
```text
You are a database query planner that takes a user's requests, and then converts to a search against the subject matter in question.
You should convert the query into:
1. A list of keywords to use against a Lucene text analyzer index, no more than 4. Strictly unigrams.
2. A question to use as the basis for a QA embedding engine.
Avoid common keywords associated with the user's subject matter.
```
7. To view the keywords and questions the **OpenAI** component generates from your collection, in the **OpenAI** component, click <Icon name="TextSearch" aria-hidden="true"/> **Inspect output**.
```
1. Keywords: features, data, attributes, characteristics
2. Question: What characteristics can be identified in my data?
```
8. To view the [DataFrame](/concepts-objects#dataframe-object) generated from the **OpenAI** component's response, in the **Structured Output** component, click <Icon name="TextSearch" aria-hidden="true"/> **Inspect output**.
The DataFrame is passed to a **Parser** component, which parses the contents of the **Keywords** column into a string.

    This string of comma-separated words is passed to the **Lexical Terms** port of the **Astra DB** component.
    Note that the **Search Query** port of the Astra DB port is connected to the **Chat Input** component from step 6.
    This **Search Query** is vectorized, and both the **Search Query** and **Lexical Terms** content are sent to the reranker at the `find_and_rerank` endpoint.

    The reranker compares the vector search results against the string of terms from the lexical search.
    The highest-ranked results of your hybrid search are returned to the **Playground**.

For more information, see the [DataStax documentation](https://docs.datastax.com/en/astra-db-serverless/databases/hybrid-search.html).

## AstraDB Graph vector store

This component implements a Vector Store using AstraDB with graph capabilities.
For more information, see the [Astra DB Serverless documentation](https://docs.datastax.com/en/astra-db-serverless/tutorials/graph-rag.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| collection_name | Collection Name | The name of the collection within AstraDB where the vectors are stored. Required. |
| token | Astra DB Application Token | Authentication token for accessing AstraDB. Required. |
| api_endpoint | API Endpoint | API endpoint URL for the AstraDB service. Required. |
| search_input | Search Input | Query string for similarity search. |
| ingest_data | Ingest Data | Data to be ingested into the vector store. |
| namespace | Namespace | Optional namespace within AstraDB to use for the collection. |
| embedding | Embedding Model | Embedding model to use. |
| metric | Metric | Distance metric for vector comparisons. The options are "cosine", "euclidean", "dot_product". |
| setup_mode | Setup Mode | Configuration mode for setting up the vector store. The options are "Sync", "Async", "Off". |
| pre_delete_collection | Pre Delete Collection | Boolean flag to determine whether to delete the collection before creating a new one. |
| number_of_results | Number of Results | Number of results to return in similarity search. Default: 4. |
| search_type | Search Type | Search type to use. The options are "Similarity", "Graph Traversal", "Hybrid". |
| traversal_depth | Traversal Depth | Maximum depth for graph traversal searches. Default: 1. |
| search_score_threshold | Search Score Threshold | Minimum similarity score threshold for search results. |
| search_filter | Search Metadata Filter | Optional dictionary of filters to apply to the search query. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | The Graph RAG vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects. |

</details>

## Cassandra

This component creates a Cassandra Vector Store with search capabilities.
For more information, see the [Cassandra documentation](https://cassandra.apache.org/doc/latest/cassandra/vector-search/overview.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| database_ref | String | Contact points for the database or AstraDB database ID. |
| username | String | Username for the database (leave empty for AstraDB). |
| token | SecretString | User password for the database or AstraDB token. |
| keyspace | String | Table Keyspace or AstraDB namespace. |
| table_name | String | Name of the table or AstraDB collection. |
| ttl_seconds | Integer | Time-to-live for added texts. |
| batch_size | Integer | Number of data to process in a single batch. |
| setup_mode | String | Configuration mode for setting up the Cassandra table. |
| cluster_kwargs | Dict | Additional keyword arguments for the Cassandra cluster. |
| search_query | String | Query for similarity search. |
| ingest_data | Data | Data to be ingested into the vector store. |
| embedding | Embeddings | Embedding function to use. |
| number_of_results | Integer | Number of results to return in search. |
| search_type | String | Type of search to perform. |
| search_score_threshold | Float | Minimum similarity score for search results. |
| search_filter | Dict | Metadata filters for search query. |
| body_search | String | Document textual search terms. |
| enable_body_search | Boolean | Flag to enable body search. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| vector_store | Cassandra | The Cassandra vector store instance configured with the specified parameters. |
| search_results | List[Data] | The results of the similarity search as a list of `Data` objects. |

</details>

## Cassandra Graph Vector Store

This component implements a Cassandra Graph Vector Store with search capabilities.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| database_ref | Contact Points / Astra Database ID | The contact points for the database or AstraDB database ID. Required. |
| username | Username | The username for the database. Leave this field empty for AstraDB. |
| token | Password / AstraDB Token | The user password for the database or AstraDB token. Required. |
| keyspace | Keyspace | The table Keyspace or AstraDB namespace. Required. |
| table_name | Table Name | The name of the table or AstraDB collection where vectors are stored. Required. |
| setup_mode | Setup Mode | The configuration mode for setting up the Cassandra table. The options are "Sync" or "Off". Default: "Sync". |
| cluster_kwargs | Cluster arguments | An optional dictionary of additional keyword arguments for the Cassandra cluster. |
| search_query | Search Query | The query string for similarity search. |
| ingest_data | Ingest Data | The list of data to be ingested into the vector store. |
| embedding | Embedding | The embedding model to use. |
| number_of_results | Number of Results | The number of results to return in similarity search. Default: 4. |
| search_type | Search Type | The search type to use. The options are "Traversal", "MMR traversal", "Similarity", "Similarity with score threshold", or "MMR (Max Marginal Relevance)". Default: "Traversal". |
| depth | Depth of traversal | The maximum depth of edges to traverse. Used for "Traversal" or "MMR traversal" search types. Default: 1. |
| search_score_threshold | Search Score Threshold | The minimum similarity score threshold for search results. Used for "Similarity with score threshold" search types. |
| search_filter | Search Metadata Filter | An optional dictionary of filters to apply to the search query. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | The Cassandra Graph vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects. |

</details>

## Chroma DB

This component creates a Chroma Vector Store with search capabilities.

The Chroma DB component creates an ephemeral vector database for experimentation and vector storage.

1. To use this component in a flow, connect it to a component that outputs **Data** or **DataFrame**.
This example splits text from a [URL](/components-data#url) component, and computes embeddings with the connected **OpenAI Embeddings** component. Chroma DB computes embeddings by default, but you can connect your own embeddings model, as seen in this example.

![ChromaDB receiving split text](/img/component-chroma-db.png)

2. In the **Chroma DB** component, in the **Collection** field, enter a name for your embeddings collection.
3. Optionally, to persist the Chroma database, in the **Persist** field, enter a directory to store the `chroma.sqlite3` file.
This example uses `./chroma-db` to create a directory relative to where Langflow is running.
4. To load data and embeddings into your Chroma database, in the **Chroma DB** component, click <Icon name="Play" aria-hidden="true"/> **Run component**.
:::tip
When loading duplicate documents, enable the **Allow Duplicates** option in Chroma DB if you want to store multiple copies of the same content, or disable it to automatically deduplicate your data.
:::
5. To view the split data, in the **Split Text** component, click <Icon name="TextSearch" aria-hidden="true"/> **Inspect output**.
6. To query your loaded data, open the **Playground** and query your database.
Your input is converted to vector data and compared to the stored vectors in a vector similarity search.

For more information, see the [Chroma documentation](https://docs.trychroma.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                         | Type          | Description                                      |
|------------------------------|---------------|--------------------------------------------------|
| collection_name               | String        | The name of the Chroma collection. Default: "langflow". |
| persist_directory             | String        | The directory to persist the Chroma database.     |
| search_query                  | String        | The query to search for in the vector store.      |
| ingest_data                   | Data          | The data to ingest into the vector store (list of `Data` objects). |
| embedding                     | Embeddings    | The embedding function to use for the vector store. |
| chroma_server_cors_allow_origins | String     | The CORS allow origins for the Chroma server.         |
| chroma_server_host            | String        | The host for the Chroma server.                       |
| chroma_server_http_port       | Integer       | The HTTP port for the Chroma server.                  |
| chroma_server_grpc_port       | Integer       | The gRPC port for the Chroma server.                  |
| chroma_server_ssl_enabled     | Boolean       | Enable SSL for the Chroma server.                 |
| allow_duplicates              | Boolean       | Allow duplicate documents in the vector store.    |
| search_type                   | String        | The type of search to perform: "Similarity" or "MMR". |
| number_of_results             | Integer       | The number of results to return from the search. Default: `10`. |
| limit                         | Integer       | The limit of the number of records to compare when `Allow Duplicates` is `False`. |

**Outputs**

| Name           | Type          | Description                    |
|----------------|---------------|--------------------------------|
| vector_store   | Chroma        | The Chroma vector store instance.  |
| search_results | List[Data]    | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.    |

</details>

## Clickhouse

This component implements a Clickhouse Vector Store with search capabilities.
For more information, see the [Clickhouse Documentation](https://clickhouse.com/docs/en/intro).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| host | hostname | The Clickhouse server hostname. Required. Default: "localhost". |
| port | port | The Clickhouse server port. Required. Default: 8123. |
| database | database | The Clickhouse database name. Required. |
| table | Table name | The Clickhouse table name. Required. |
| username | The ClickHouse user name. | Username for authentication. Required. |
| password | The password for username. | Password for authentication. Required. |
| index_type | index_type | Type of the index. The options are "annoy" and "vector_similarity". Default: "annoy". |
| metric | metric | Metric to compute distance. The options are "angular", "euclidean", "manhattan", "hamming", "dot". Default: "angular". |
| secure | Use https/TLS | Overrides inferred values from the interface or port arguments. Default: false. |
| index_param | Param of the index | Index parameters. Default: "'L2Distance',100". |
| index_query_params | index query params | Additional index query parameters. |
| search_query | Search Query | The query string for similarity search. |
| ingest_data | Ingest Data | The data to be ingested into the vector store. |
| embedding | Embedding | The embedding model to use. |
| number_of_results | Number of Results | The number of results to return in similarity search. Default: 4. |
| score_threshold | Score threshold | The threshold for similarity scores. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | The Clickhouse vector store. |
| search_results | Search Results | The results of the similarity search as a list of Data objects. |

</details>

## Couchbase

This component creates a Couchbase Vector Store with search capabilities.
For more information, see the [Couchbase documentation](https://docs.couchbase.com/home/index.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                    | Type          | Description                                      |
|-------------------------|---------------|--------------------------------------------------|
| couchbase_connection_string | SecretString | Couchbase Cluster connection string. Required.   |
| couchbase_username       | String        | Couchbase username. Required.                   |
| couchbase_password       | SecretString  | Couchbase password. Required.                   |
| bucket_name              | String        | Name of the Couchbase bucket. Required.         |
| scope_name               | String        | Name of the Couchbase scope. Required.          |
| collection_name          | String        | Name of the Couchbase collection. Required.     |
| index_name               | String        | Name of the Couchbase index. Required.          |
| search_query             | String        | The query to search for in the vector store.     |
| ingest_data              | Data          | The list of data to ingest into the vector store. |
| embedding                | Embeddings    | The embedding function to use for the vector store. |
| number_of_results        | Integer       | Number of results to return from the search. Default: 4. |

**Outputs**

| Name           | Type                   | Description                    |
|----------------|------------------------|--------------------------------|
| vector_store   | CouchbaseVectorStore    | A Couchbase vector store instance configured with the specified parameters. |

</details>

## Local DB

The **Local DB** component is Langflow's enhanced version of Chroma DB.

The component adds a user-friendly interface with two modes (Ingest and Retrieve), automatic collection management, and built-in persistence in Langflow's cache directory.

Local DB includes **Ingest** and **Retrieve** modes.

The **Ingest** mode works similarly to [ChromaDB](#chroma-db), and persists your database to the Langflow cache directory. The Langflow cache directory location is specified in `LANGFLOW_CONFIG_DIR`. For more information, see [Environment variables](/environment-variables).

The **Retrieve** mode can query your **Chroma DB** collections.

![Local DB retrieving vectors](/img/component-local-db.png)

For more information, see the [Chroma documentation](https://docs.trychroma.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| collection_name | String | The name of the Chroma collection. Default: "langflow". |
| persist_directory | String | Custom base directory to save the vector store. Collections are stored under `$DIRECTORY/vector_stores/$COLLECTION_NAME`. If not specified, it uses your system's cache folder. |
| existing_collections | String | Select a previously created collection to search through its stored data. |
| embedding | Embeddings | The embedding function to use for the vector store. |
| allow_duplicates | Boolean | If false, will not add documents that are already in the Vector Store. |
| search_type | String | Type of search to perform: "Similarity" or "MMR". |
| ingest_data | Data/DataFrame | Data to store. It is embedded and indexed for semantic search. |
| search_query | String | Enter text to search for similar content in the selected collection. |
| number_of_results | Integer | Number of results to return. Default: 10. |
| limit | Integer | Limit the number of records to compare when Allow Duplicates is False. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| vector_store | Chroma | A local Chroma vector store instance configured with the specified parameters. |
| search_results | List[Data](/concepts-objects#data-object) | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.  |

</details>

## Elasticsearch

This component creates an Elasticsearch Vector Store with search capabilities.
For more information, see the [Elasticsearch documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| es_url | String | Elasticsearch server URL. |
| es_user | String | Username for Elasticsearch authentication. |
| es_password | SecretString | Password for Elasticsearch authentication. |
| index_name | String | Name of the Elasticsearch index. |
| strategy | String | Strategy for vector search. The options are "approximate_k_nearest_neighbors" or "script_scoring". |
| distance_strategy | String | Strategy for distance calculation. The options are "COSINE", "EUCLIDEAN_DISTANCE", or "DOT_PRODUCT". |
| search_query | String | Query for similarity search. |
| ingest_data | Data | Data to be ingested into the vector store. |
| embedding | Embeddings | Embedding function to use. |
| number_of_results | Integer | Number of results to return in search. Default: `4`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| vector_store | ElasticsearchStore | The Elasticsearch vector store instance. |
| search_results | List[Data] | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.  |

</details>

## FAISS

This component creates a FAISS Vector Store with search capabilities.
For more information, see the [FAISS documentation](https://faiss.ai/index.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                      | Type          | Description                                      |
|---------------------------|---------------|--------------------------------------------------|
| index_name                 | String        | The name of the FAISS index. Default: "langflow_index". |
| persist_directory          | String        | Path to save the FAISS index. It is relative to where Langflow is running. |
| search_query               | String        | The query to search for in the vector store.     |
| ingest_data                | Data          | The list of data to ingest into the vector store. |
| allow_dangerous_deserialization | Boolean  | Set to True to allow loading pickle files from untrusted sources. Default: True. |
| embedding                  | Embeddings    | The embedding function to use for the vector store. |
| number_of_results          | Integer       | Number of results to return from the search. Default: 4. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | The FAISS vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects. |

</details>

## Graph RAG

This component performs Graph RAG (Retrieval Augmented Generation) traversal in a vector store, enabling graph-based document retrieval.
For more information, see the [Graph RAG documentation](https://datastax.github.io/graph-rag/).

For an example flow, see the **Graph RAG** template.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| embedding_model | Embedding Model | Specify the embedding model. This is not required for collections embedded with [Astra vectorize](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html). |
| vector_store | Vector Store Connection | Connection to the vector store. |
| edge_definition | Edge Definition | Edge definition for the graph traversal. For more information, see the [GraphRAG documentation](https://datastax.github.io/graph-rag/reference/graph_retriever/edges/). |
| strategy | Traversal Strategies | The strategy to use for graph traversal. Strategy options are dynamically loaded from available strategies. |
| search_query | Search Query | The query to search for in the vector store. |
| graphrag_strategy_kwargs | Strategy Parameters | Optional dictionary of additional parameters for the retrieval strategy. For more information, see the [strategy documentation](https://datastax.github.io/graph-rag/reference/graph_retriever/strategies/). |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| search_results | List[Data] | Results of the graph-based document retrieval as a list of [Data](/concepts-objects#data-object) objects. |

</details>

## Hyper-Converged Database (HCD)

This component implements a Vector Store using HCD.

To use the HCD vector store, add your deployment's collection name, username, password, and HCD Data API endpoint.
The endpoint must be formatted like `http[s]://**DOMAIN_NAME** or **IP_ADDRESS**[:port]`, for example, `http://192.0.2.250:8181`.

Replace **DOMAIN_NAME** or **IP_ADDRESS** with the domain name or IP address of your HCD Data API connection.

To use the HCD vector store for embeddings ingestion, connect it to an embeddings model and a file loader:

![HCD vector store embeddings ingestion](/img/component-hcd-example-flow.png)

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| collection_name | Collection Name | The name of the collection within HCD where the vectors will be stored. Required. |
| username | HCD Username | Authentication username for accessing HCD. Default is "hcd-superuser". Required. |
| password | HCD Password | Authentication password for accessing HCD. Required. |
| api_endpoint | HCD API Endpoint | API endpoint URL for the HCD service. Required. |
| search_input | Search Input | Query string for similarity search. |
| ingest_data | Ingest Data | Data to be ingested into the vector store. |
| namespace | Namespace | Optional namespace within HCD to use for the collection. Default is "default_namespace". |
| ca_certificate | CA Certificate | Optional CA certificate for TLS connections to HCD. |
| metric | Metric | Optional distance metric for vector comparisons. Options are "cosine", "dot_product", "euclidean". |
| batch_size | Batch Size | Optional number of data to process in a single batch. |
| bulk_insert_batch_concurrency | Bulk Insert Batch Concurrency | Optional concurrency level for bulk insert operations. |
| bulk_insert_overwrite_concurrency | Bulk Insert Overwrite Concurrency | Optional concurrency level for bulk insert operations that overwrite existing data. |
| bulk_delete_concurrency | Bulk Delete Concurrency | Optional concurrency level for bulk delete operations. |
| setup_mode | Setup Mode | Configuration mode for setting up the vector store. Options are "Sync", "Async", "Off". Default is "Sync". |
| pre_delete_collection | Pre Delete Collection | Boolean flag to determine whether to delete the collection before creating a new one. |
| metadata_indexing_include | Metadata Indexing Include | Optional list of metadata fields to include in the indexing. |
| embedding | Embedding or Astra Vectorize | Allows either an embedding model or an Astra Vectorize configuration. |
| metadata_indexing_exclude | Metadata Indexing Exclude | Optional list of metadata fields to exclude from the indexing. |
| collection_indexing_policy | Collection Indexing Policy | Optional dictionary defining the indexing policy for the collection. |
| number_of_results | Number of Results | Number of results to return in similarity search. Default is 4. |
| search_type | Search Type | Search type to use. Options are "Similarity", "Similarity with score threshold", "MMR (Max Marginal Relevance)". Default is "Similarity". |
| search_score_threshold | Search Score Threshold | Minimum similarity score threshold for search results. Default is 0. |
| search_filter | Search Metadata Filter | Optional dictionary of filters to apply to the search query. |

**Outputs**

| Name          | Type         | Description                               |
|---------------|--------------|-------------------------------------------|
| vector_store  | HyperConvergedDatabaseVectorStore | The HCD vector store instance. |
| search_results| List[Data]   | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.               |

</details>

## Milvus

This component creates a Milvus Vector Store with search capabilities.
For more information, see the [Milvus documentation](https://milvus.io/docs).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                    | Type          | Description                                      |
|-------------------------|---------------|--------------------------------------------------|
| collection_name          | String        | Name of the Milvus collection.                   |
| collection_description   | String        | Description of the Milvus collection.            |
| uri                      | String        | Connection URI for Milvus.                       |
| password                 | SecretString  | Password for Milvus.                             |
| username                 | SecretString  | Username for Milvus.                             |
| batch_size               | Integer       | Number of data to process in a single batch.     |
| search_query             | String        | Query for similarity search.                     |
| ingest_data              | Data          | Data to be ingested into the vector store.       |
| embedding                | Embeddings    | Embedding function to use.                       |
| number_of_results        | Integer       | Number of results to return in search.           |
| search_type              | String        | Type of search to perform.                       |
| search_score_threshold   | Float         | Minimum similarity score for search results.     |
| search_filter            | Dict          | Metadata filters for search query.               |
| setup_mode               | String        | Configuration mode for setting up the vector store. |
| vector_dimensions        | Integer       | Number of dimensions of the vectors.             |
| pre_delete_collection    | Boolean       | Whether to delete the collection before creating a new one. |

**Outputs**

| Name           | Type                   | Description                    |
|----------------|------------------------|--------------------------------|
| vector_store   | Milvus                 | A Milvus vector store instance configured with the specified parameters. |

</details>

## MongoDB Atlas

This component creates a MongoDB Atlas Vector Store with search capabilities.
For more information, see the [MongoDB Atlas documentation](https://www.mongodb.com/docs/atlas/atlas-vector-search/tutorials/vector-search-quick-start/).

<details>
<summary>Parameters</summary>

**Inputs**
| Name                      | Type         | Description                               |
| ------------------------- | ------------ | ----------------------------------------- |
| mongodb_atlas_cluster_uri | SecretString | The connection URI for your MongoDB Atlas cluster. Required. |
| enable_mtls               | Boolean      | Enable mutual TLS authentication. Default: false. |
| mongodb_atlas_client_cert | SecretString | Client certificate combined with private key for mTLS authentication. Required if mTLS is enabled. |
| db_name                   | String       | The name of the database to use. Required. |
| collection_name           | String       | The name of the collection to use. Required. |
| index_name                | String       | The name of the Atlas Search index, it should be a Vector Search. Required. |
| insert_mode               | String       | How to insert new documents into the collection. The options are "append" or "overwrite". Default: "append". |
| embedding                 | Embeddings   | The embedding model to use. |
| number_of_results         | Integer      | Number of results to return in similarity search. Default: 4. |
| index_field               | String       | The field to index. Default: "embedding". |
| filter_field              | String       | The field to filter the index. |
| number_dimensions         | Integer      | Embedding context length. Default: 1536. |
| similarity                | String       | The method used to measure similarity between vectors. The options are "cosine", "euclidean", or "dotProduct". Default: "cosine". |
| quantization              | String       | Quantization reduces memory costs by converting 32-bit floats to smaller data types. The options are "scalar" or "binary". |

**Outputs**

| Name          | Type                   | Description                               |
| ------------- | ---------------------- | ----------------------------------------- |
| vector_store  | MongoDBAtlasVectorSearch| The MongoDB Atlas vector store instance.       |
| search_results| List[Data]             | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.               |

</details>

## Opensearch

This component creates an Opensearch vector store with search capabilities
For more information, see [Opensearch documentation](https://opensearch.org/platform/search/vector-database.html).

<details>
<summary>Parameters</summary>

**Inputs**
| Name                   | Type         | Description                                                                                                            |
|------------------------|--------------|------------------------------------------------------------------------------------------------------------------------|
| opensearch_url         | String       | URL for OpenSearch cluster, such as `https://192.168.1.1:9200`.                                                             |
| index_name             | String       | The index name where the vectors are stored in OpenSearch cluster.                                                  |
| search_input           | String       | Enter a search query. Leave empty to retrieve all documents or if hybrid search is being used.                          |
| ingest_data            | Data         | The data to be ingested into the vector store.                                                                              |
| embedding              | Embeddings   | The embedding function to use.                                                                                              |
| search_type            | String       | The options are "similarity", "similarity_score_threshold", "mmr".                                                     |
| number_of_results      | Integer      | The number of results to return in search.                                                                                  |
| search_score_threshold | Float        | The minimum similarity score threshold for search results.                                                                  |
| username               | String       | The username for the opensource cluster.                                                                                    |
| password               | SecretString | The password for the opensource cluster.                                                                                    |
| use_ssl                | Boolean      | Use SSL.                                                                                                                |
| verify_certs           | Boolean      | Verify certificates.                                                                                                    |
| hybrid_search_query    | String       | Provide a custom hybrid search query in JSON format. This allows you to combine vector similarity and keyword matching. |

**Outputs**

| Name          | Type                   | Description                                 |
| ------------- |------------------------|---------------------------------------------|
| vector_store  | OpenSearchVectorSearch | OpenSearch vector store instance            |
| search_results| List[Data]             | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.                 |

</details>

## PGVector

This component creates a PGVector Vector Store with search capabilities.
For more information, see the [PGVector documentation](https://github.com/pgvector/pgvector).

<details>
<summary>Parameters</summary>

**Inputs**

| Name            | Type         | Description                               |
| --------------- | ------------ | ----------------------------------------- |
| pg_server_url   | SecretString | The PostgreSQL server connection string.       |
| collection_name | String       | The table name for the vector store.           |
| search_query    | String       | The query for similarity search.               |
| ingest_data     | Data         | The data to be ingested into the vector store. |
| embedding       | Embeddings   | The embedding function to use.                 |
| number_of_results | Integer    | The number of results to return in search.     |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | The PGVector vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects. |

</details>

## Pinecone

This component creates a Pinecone Vector Store with search capabilities.
For more information, see the [Pinecone documentation](https://docs.pinecone.io/home).

<details>
<summary>Parameters</summary>

**Inputs**

| Name              | Type         | Description                               |
| ----------------- | ------------ | ----------------------------------------- |
| index_name        | String       | The name of the Pinecone index.                |
| namespace         | String       | The namespace for the index.                   |
| distance_strategy | String       | The strategy for calculating distance between vectors. |
| pinecone_api_key  | SecretString | The API key for Pinecone.                      |
| text_key          | String       | The key in the record to use as text.          |
| search_query      | String       | The query for similarity search.               |
| ingest_data       | Data         | The data to be ingested into the vector store. |
| embedding         | Embeddings   | The embedding function to use.                 |
| number_of_results | Integer      | The number of results to return in search.     |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | The Pinecone vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects. |

</details>

## Qdrant

This component creates a Qdrant Vector Store with search capabilities.
For more information, see the [Qdrant documentation](https://qdrant.tech/documentation/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                 | Type         | Description                               |
| -------------------- | ------------ | ----------------------------------------- |
| collection_name       | String       | The name of the Qdrant collection.             |
| host                 | String       | The Qdrant server host.                        |
| port                 | Integer      | The Qdrant server port.                        |
| grpc_port            | Integer      | The Qdrant gRPC port.                          |
| api_key              | SecretString | The API key for Qdrant.                        |
| prefix               | String       | The prefix for Qdrant.                         |
| timeout              | Integer      | The timeout for Qdrant operations.             |
| path                 | String       | The path for Qdrant.                           |
| url                  | String       | The URL for Qdrant.                            |
| distance_func        | String       | The distance function for vector similarity.   |
| content_payload_key  | String       | The content payload key.                  |
| metadata_payload_key | String       | The metadata payload key.                 |
| search_query         | String       | The query for similarity search.               |
| ingest_data          | Data         | The data to be ingested into the vector store. |
| embedding            | Embeddings   | The embedding function to use.                 |
| number_of_results    | Integer      | The number of results to return in search.     |

**Outputs**

| Name          | Type     | Description                               |
| ------------- | -------- | ----------------------------------------- |
| vector_store  | Qdrant   | A Qdrant vector store instance.              |
| search_results| List[Data] | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.             |

</details>

## Redis

This component creates a Redis Vector Store with search capabilities.
For more information, see the [Redis documentation](https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/vectors/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name              | Type         | Description                               |
| ----------------- | ------------ | ----------------------------------------- |
| redis_server_url  | SecretString | The Redis server connection string.            |
| redis_index_name  | String       | The name of the Redis index.                   |
| code              | String       | The custom code for Redis (advanced).          |
| schema            | String       | The schema for Redis index.                    |
| search_query      | String       | The query for similarity search.               |
| ingest_data       | Data         | The data to be ingested into the vector store. |
| number_of_results | Integer      | The number of results to return in search.     |
| embedding         | Embeddings   | The embedding function to use.                 |

**Outputs**

| Name          | Type     | Description                               |
| ------------- | -------- | ----------------------------------------- |
| vector_store  | Redis    | Redis vector store instance               |
| search_results| List[Data] | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.              |

</details>

## Supabase

This component creates a connection to a Supabase Vector Store with search capabilities.
For more information, see the [Supabase documentation](https://supabase.com/docs/guides/ai).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                | Type         | Description                               |
| ------------------- | ------------ | ----------------------------------------- |
| supabase_url        | String       | The URL of the Supabase instance.              |
| supabase_service_key| SecretString | The service key for Supabase authentication.   |
| table_name          | String       | The name of the table in Supabase.             |
| query_name          | String       | The name of the query to use.                  |
| search_query        | String       | The query for similarity search.               |
| ingest_data         | Data         | The data to be ingested into the vector store. |
| embedding           | Embeddings   | The embedding function to use.                 |
| number_of_results   | Integer      | The number of results to return in search.     |

**Outputs**

| Name          | Type               | Description                               |
| ------------- | ------------------ | ----------------------------------------- |
| vector_store  | SupabaseVectorStore | A Supabase vector store instance.            |
| search_results| List[Data]          | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.               |

</details>

## Upstash

This component creates an Upstash Vector Store with search capabilities.
For more information, see the [Upstash documentation](https://upstash.com/docs/introduction).

<details>
<summary>Parameters</summary>

**Inputs**

| Name            | Type         | Description                               |
| --------------- | ------------ | ----------------------------------------- |
| index_url       | String       | The URL of the Upstash index.              |
| index_token     | SecretString | The token for the Upstash index.           |
| text_key        | String       | The key in the record to use as text.      |
| namespace       | String       | The namespace for the index.                   |
| search_query    | String       | The query for similarity search.               |
| metadata_filter | String       | Filter documents by metadata.             |
| ingest_data     | Data         | The data to be ingested into the vector store. |
| embedding       | Embeddings   | The embedding function to use.      |
| number_of_results | Integer    | The number of results to return in search.     |

**Outputs**

| Name          | Type             | Description                               |
| ------------- | ---------------- | ----------------------------------------- |
| vector_store  | UpstashVectorStore| An Upstash vector store instance.             |
| search_results| List[Data]        | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.               |

</details>

## Vectara

This component creates a Vectara Vector Store with search capabilities.
For more information, see the [Vectara documentation](https://docs.vectara.com/docs/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name             | Type         | Description                               |
| ---------------- | ------------ | ----------------------------------------- |
| vectara_customer_id | String     | The Vectara customer ID.                       |
| vectara_corpus_id   | String     | The Vectara corpus ID.                         |
| vectara_api_key   | SecretString | The Vectara API key.                           |
| embedding         | Embeddings   | The embedding function to use (optional).      |
| ingest_data       | List[Document/Data] | The data to be ingested into the vector store. |
| search_query      | String       | The query for similarity search.               |
| number_of_results | Integer      | The number of results to return in search.     |

**Outputs**

| Name          | Type              | Description                               |
| ------------- | ----------------- | ----------------------------------------- |
| vector_store  | VectaraVectorStore | Vectara vector store instance.             |
| search_results| List[Data]         | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.               |

</details>

## Vectara Search

This component searches a Vectara Vector Store for documents based on the provided input.
For more information, see the [Vectara documentation](https://docs.vectara.com/docs/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name                | Type         | Description                               |
|---------------------|--------------|-------------------------------------------|
| search_type         | String       | The type of search, such as "Similarity" or "MMR". |
| input_value         | String       | The search query.                              |
| vectara_customer_id | String       | The Vectara customer ID.                       |
| vectara_corpus_id   | String       | The Vectara corpus ID.                         |
| vectara_api_key     | SecretString | The Vectara API key.                           |
| files_url           | List[String] | Optional URLs for file initialization.     |

**Outputs**

| Name           | Type       | Description                |
|----------------|------------|----------------------------|
| search_results | List[Data] | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.  |

</details>

## Weaviate

This component facilitates a Weaviate Vector Store setup, optimizing text and document indexing and retrieval.
For more information, see the [Weaviate Documentation](https://weaviate.io/developers/weaviate).

<details>
<summary>Parameters</summary>

**Inputs**

| Name          | Type         | Description                               |
|---------------|--------------|-------------------------------------------|
| weaviate_url  | String       | The default instance URL.                      |
| search_by_text| Boolean      | Indicates whether to search by text.       |
| api_key       | SecretString | The optional API key for authentication.       |
| index_name    | String       | The optional index name.                       |
| text_key      | String       | The default text extraction key.               |
| input         | Document     | The document or record.                        |
| embedding     | Embeddings   | The embedding model used.                                |
| attributes    | List[String] | Optional additional attributes.            |

**Outputs**

| Name         | Type             | Description                   |
|--------------|------------------|-------------------------------|
| vector_store | WeaviateVectorStore | The Weaviate vector store instance. |

</details>

## Weaviate Search

This component searches a Weaviate Vector Store for documents similar to the input.
For more information, see the [Weaviate Documentation](https://weaviate.io/developers/weaviate).

<details>
<summary>Parameters</summary>

**Inputs**

| Name          | Type         | Description                               |
|---------------|--------------|-------------------------------------------|
| search_type   | String       | The type of search, such as "Similarity" or "MMR" |
| input_value   | String       | The search query.                              |
| weaviate_url  | String       | The default instance URL.                      |
| search_by_text| Boolean      | A boolean value that indicates whether to search by text.       |
| api_key       | SecretString | The optional API key for authentication.       |
| index_name    | String       | The optional index name.                       |
| text_key      | String       | The default text extraction key.               |
| embedding     | Embeddings   | The embeddings model used.                                |
| attributes    | List[String] | Optional additional attributes.            |

**Outputs**

| Name           | Type       | Description                |
|----------------|------------|----------------------------|
| search_results | List[Data] | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects.  |

</details>