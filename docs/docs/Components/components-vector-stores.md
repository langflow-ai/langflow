---
title: Vector stores
slug: /components-vector-stores
---

import Icon from "@site/src/components/icon";

# Vector store components in Langflow

Vector databases store vector data, which backs AI workloads like chatbots and Retrieval Augmented Generation.

Vector database components establish connections to existing vector databases or create in-memory vector stores for storing and retrieving vector data.

Vector database components are distinct from [memory components](/components-memories), which are built specifically for storing and retrieving chat messages from external databases.

## Use a vector store component in a flow

This example uses the **Astra DB vector store** component. Your vector store component's parameters and authentication may be different, but the document ingestion workflow is the same. A document is loaded from a local machine and chunked. The Astra DB vector store generates embeddings with the connected [model](/components-models) component, and stores them in the connected Astra DB database.

This vector data can then be retrieved for workloads like Retrieval Augmented Generation.

![](/img/vector-store-retrieval.png)

The user's chat input is embedded and compared to the vectors embedded during document ingestion for a similarity search.
The results are output from the vector database component as a [Data](/concepts-objects) object and parsed into text.
This text fills the `{context}` variable in the **Prompt** component, which informs the **Open AI model** component's responses.

Alternatively, connect the vector database component's **Retriever** port to a [retriever tool](components-tools#retriever-tool), and then to an [agent](/components-agents) component. This enables the agent to use your vector database as a tool and make decisions based on the available data.

![](/img/vector-store-agent-retrieval-tool.png)

## Astra DB Vector Store

This component implements a Vector Store using Astra DB with search capabilities.

For more information, see the [DataStax documentation](https://docs.datastax.com/en/astra-db-serverless/databases/create-database.html).

### Inputs

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
| number_of_results | Number of Search Results | The number of search results to return (default: `4`). |
| search_type | Search Type | The search type to use. The options are `Similarity`, `Similarity with score threshold`, and `MMR (Max Marginal Relevance)`. |
| search_score_threshold | Search Score Threshold | The minimum similarity score threshold for search results when using the `Similarity with score threshold` option. |
| advanced_search_filter | Search Metadata Filter | An optional dictionary of filters to apply to the search query. |
| autodetect_collection | Autodetect Collection | A boolean flag to determine whether to autodetect the collection. |
| content_field | Content Field | A field to use as the text content field for the vector store. |
| deletion_field | Deletion Based On Field | When provided, documents in the target collection with metadata field values matching the input metadata field value are deleted before new data is loaded. |
| ignore_invalid_documents | Ignore Invalid Documents | A boolean flag to determine whether to ignore invalid documents at runtime. |
| astradb_vectorstore_kwargs | AstraDBVectorStore Parameters | An optional dictionary of additional parameters for the AstraDBVectorStore. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | Astra DB vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of [Data](/concepts-objects#data-object) objects. |

### Generate embeddings

The **Astra DB Vector Store** component offers two methods for generating embeddings.

1. **Embedding Model**: Use your own embedding model by connecting an [Embeddings](/components-embedding-models) component in Langflow.

2. **Astra Vectorize**: Use Astra DB's built-in embedding generation service. When creating a new collection, choose the embeddings provider and models, including NVIDIA's `NV-Embed-QA` model hosted by Datastax.

:::important
The embedding model selection is made when creating a new collection and cannot be changed later.
:::

For an example of using the **Astra DB Vector Store** component with an embedding model, see the [Vector Store RAG starter project](/starter-projects-vector-store-rag).

For more information, see the [Astra DB Serverless documentation](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html).

### Hybrid search

The **Astra DB** component includes **hybrid search**, which is enabled by default.

The component fields related to hybrid search are **Search Query**, **Lexical Terms**, and **Reranker**.

* **Search Query** finds results by vector similarity.
* **Lexical Terms** is a comma-separated string of keywords, like `features, data, attributes, characteristics`.
* **Reranker** is the re-ranker model used in the hybrid search.
The re-ranker model is `nvidia/llama-3.2-nv.reranker`.

[Hybrid search](https://docs.datastax.com/en/astra-db-serverless/databases/hybrid-search.html) performs a vector similarity search and a lexical search, compares the results of both searches, and then returns the most relevant results overall.

To use **Hybrid search** in the **Astra DB** component, do the following:

1. Click **New Flow** > **RAG** > **Hybrid Search RAG**.
2. In the **OpenAI** model component, add your **OpenAI API key**.
3. In the **Astra DB** vector store component, add your **Astra DB Application Token**.
4. In the **Database** field, select your database.
5. In the **Collection** field, select the collection you want to search.
You must enable support for hybrid search when you create the collection.
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
7. To view the keywords and questions the **OpenAI** component generates from your collection, in the **OpenAI** component, click <Icon name="TextSearch" aria-label="Inspect icon" />.
```
1. Keywords: features, data, attributes, characteristics
2. Question: What characteristics can be identified in my data?
```
8. To view the [DataFrame](/concepts-objects#dataframe-object) generated from the **OpenAI** component's response, in the **Structured Output** component, click <Icon name="TextSearch" aria-label="Inspect icon" />.
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

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| collection_name | Collection Name | The name of the collection within AstraDB where the vectors will be stored (required) |
| token | Astra DB Application Token | Authentication token for accessing AstraDB (required) |
| api_endpoint | API Endpoint | API endpoint URL for the AstraDB service (required) |
| search_input | Search Input | Query string for similarity search |
| ingest_data | Ingest Data | Data to be ingested into the vector store |
| namespace | Namespace | Optional namespace within AstraDB to use for the collection |
| embedding | Embedding Model | Embedding model to use |
| metric | Metric | Distance metric for vector comparisons (options: "cosine", "euclidean", "dot_product") |
| setup_mode | Setup Mode | Configuration mode for setting up the vector store (options: "Sync", "Async", "Off") |
| pre_delete_collection | Pre Delete Collection | Boolean flag to determine whether to delete the collection before creating a new one |
| number_of_results | Number of Results | Number of results to return in similarity search (default: 4) |
| search_type | Search Type | Search type to use (options: "Similarity", "Graph Traversal", "Hybrid") |
| traversal_depth | Traversal Depth | Maximum depth for graph traversal searches (default: 1) |
| search_score_threshold | Search Score Threshold | Minimum similarity score threshold for search results |
| search_filter | Search Metadata Filter | Optional dictionary of filters to apply to the search query |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | Astra DB graph vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of `Data` objects. |


## Cassandra

This component creates a Cassandra Vector Store with search capabilities.
For more information, see the [Cassandra documentation](https://cassandra.apache.org/doc/latest/cassandra/vector-search/overview.html).

### Inputs

| Name | Type | Description |
|------|------|-------------|
| database_ref | String | Contact points for the database or AstraDB database ID |
| username | String | Username for the database (leave empty for AstraDB) |
| token | SecretString | User password for the database or AstraDB token |
| keyspace | String | Table Keyspace or AstraDB namespace |
| table_name | String | Name of the table or AstraDB collection |
| ttl_seconds | Integer | Time-to-live for added texts |
| batch_size | Integer | Number of data to process in a single batch |
| setup_mode | String | Configuration mode for setting up the Cassandra table |
| cluster_kwargs | Dict | Additional keyword arguments for the Cassandra cluster |
| search_query | String | Query for similarity search |
| ingest_data | Data | Data to be ingested into the vector store |
| embedding | Embeddings | Embedding function to use |
| number_of_results | Integer | Number of results to return in search |
| search_type | String | Type of search to perform |
| search_score_threshold | Float | Minimum similarity score for search results |
| search_filter | Dict | Metadata filters for search query |
| body_search | String | Document textual search terms |
| enable_body_search | Boolean | Flag to enable body search |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| vector_store | Cassandra | A Cassandra vector store instance configured with the specified parameters. |
| search_results | List[Data] | The results of the similarity search as a list of `Data` objects. |

## Cassandra Graph Vector Store

This component implements a Cassandra Graph Vector Store with search capabilities.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| database_ref | Contact Points / Astra Database ID | Contact points for the database or AstraDB database ID (required) |
| username | Username | Username for the database (leave empty for AstraDB) |
| token | Password / AstraDB Token | User password for the database or AstraDB token (required) |
| keyspace | Keyspace | Table Keyspace or AstraDB namespace (required) |
| table_name | Table Name | The name of the table or AstraDB collection where vectors will be stored (required) |
| setup_mode | Setup Mode | Configuration mode for setting up the Cassandra table (options: "Sync", "Off", default: "Sync") |
| cluster_kwargs | Cluster arguments | Optional dictionary of additional keyword arguments for the Cassandra cluster |
| search_query | Search Query | Query string for similarity search |
| ingest_data | Ingest Data | Data to be ingested into the vector store (list of Data objects) |
| embedding | Embedding | Embedding model to use |
| number_of_results | Number of Results | Number of results to return in similarity search (default: 4) |
| search_type | Search Type | Search type to use (options: "Traversal", "MMR traversal", "Similarity", "Similarity with score threshold", "MMR (Max Marginal Relevance)", default: "Traversal") |
| depth | Depth of traversal | The maximum depth of edges to traverse (for "Traversal" or "MMR traversal" search types, default: 1) |
| search_score_threshold | Search Score Threshold | Minimum similarity score threshold for search results (for "Similarity with score threshold" search type) |
| search_filter | Search Metadata Filter | Optional dictionary of filters to apply to the search query |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | A Cassandra Graph vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of `Data` objects. |

## Chroma DB

This component creates a Chroma Vector Store with search capabilities.
For more information, see the [Chroma documentation](https://docs.trychroma.com/).

### Inputs

| Name                         | Type          | Description                                      |
|------------------------------|---------------|--------------------------------------------------|
| collection_name               | String        | The name of the Chroma collection. Default: "langflow". |
| persist_directory             | String        | The directory to persist the Chroma database.     |
| search_query                  | String        | The query to search for in the vector store.      |
| ingest_data                   | Data          | The data to ingest into the vector store (list of Data objects). |
| embedding                     | Embeddings    | The embedding function to use for the vector store. |
| chroma_server_cors_allow_origins | String     | CORS allow origins for the Chroma server.         |
| chroma_server_host            | String        | Host for the Chroma server.                       |
| chroma_server_http_port       | Integer       | HTTP port for the Chroma server.                  |
| chroma_server_grpc_port       | Integer       | gRPC port for the Chroma server.                  |
| chroma_server_ssl_enabled     | Boolean       | Enable SSL for the Chroma server.                 |
| allow_duplicates              | Boolean       | Allow duplicate documents in the vector store.    |
| search_type                   | String        | Type of search to perform: "Similarity" or "MMR". |
| number_of_results             | Integer       | Number of results to return from the search. Default: 10. |
| limit                         | Integer       | Limit the number of records to compare when Allow Duplicates is False. |

### Outputs

| Name           | Type          | Description                    |
|----------------|---------------|--------------------------------|
| vector_store   | Chroma        | Chroma vector store instance   |
| search_results | List[Data]    | Results of similarity search   |

## Clickhouse

This component implements a Clickhouse Vector Store with search capabilities.
For more information, see the [CLickhouse Documentation](https://clickhouse.com/docs/en/intro).

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| host | hostname | Clickhouse server hostname (required, default: "localhost") |
| port | port | Clickhouse server port (required, default: 8123) |
| database | database | Clickhouse database name (required) |
| table | Table name | Clickhouse table name (required) |
| username | The ClickHouse user name. | Username for authentication (required) |
| password | The password for username. | Password for authentication (required) |
| index_type | index_type | Type of the index (options: "annoy", "vector_similarity", default: "annoy") |
| metric | metric | Metric to compute distance (options: "angular", "euclidean", "manhattan", "hamming", "dot", default: "angular") |
| secure | Use https/TLS | Overrides inferred values from the interface or port arguments (default: false) |
| index_param | Param of the index | Index parameters (default: "'L2Distance',100") |
| index_query_params | index query params | Additional index query parameters |
| search_query | Search Query | Query string for similarity search |
| ingest_data | Ingest Data | Data to be ingested into the vector store |
| embedding | Embedding | Embedding model to use |
| number_of_results | Number of Results | Number of results to return in similarity search (default: 4) |
| score_threshold | Score threshold | Threshold for similarity scores |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | Built Clickhouse vector store |
| search_results | Search Results | Results of the similarity search as a list of Data objects |

## Couchbase

This component creates a Couchbase Vector Store with search capabilities.
For more information, see the [Couchbase documentation](https://docs.couchbase.com/home/index.html).

### Inputs

| Name                    | Type          | Description                                      |
|-------------------------|---------------|--------------------------------------------------|
| couchbase_connection_string | SecretString | Couchbase Cluster connection string (required).   |
| couchbase_username       | String        | Couchbase username (required).                   |
| couchbase_password       | SecretString  | Couchbase password (required).                   |
| bucket_name              | String        | Name of the Couchbase bucket (required).         |
| scope_name               | String        | Name of the Couchbase scope (required).          |
| collection_name          | String        | Name of the Couchbase collection (required).     |
| index_name               | String        | Name of the Couchbase index (required).          |
| search_query             | String        | The query to search for in the vector store.     |
| ingest_data              | Data          | The data to ingest into the vector store (list of Data objects). |
| embedding                | Embeddings    | The embedding function to use for the vector store. |
| number_of_results        | Integer       | Number of results to return from the search. Default: 4 (advanced). |

### Outputs

| Name           | Type                   | Description                    |
|----------------|------------------------|--------------------------------|
| vector_store   | CouchbaseVectorStore    | A Couchbase vector store instance configured with the specified parameters. |


## Elasticsearch

This component creates an Elasticsearch Vector Store with search capabilities.
For more information, see the [Elasticsearch documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html).

### Inputs

| Name | Type | Description |
|------|------|-------------|
| es_url | String | Elasticsearch server URL |
| es_user | String | Username for Elasticsearch authentication |
| es_password | SecretString | Password for Elasticsearch authentication |
| index_name | String | Name of the Elasticsearch index |
| strategy | String | Strategy for vector search ("approximate_k_nearest_neighbors" or "script_scoring") |
| distance_strategy | String | Strategy for distance calculation ("COSINE", "EUCLIDEAN_DISTANCE", "DOT_PRODUCT") |
| search_query | String | Query for similarity search |
| ingest_data | Data | Data to be ingested into the vector store |
| embedding | Embeddings | Embedding function to use |
| number_of_results | Integer | Number of results to return in search (default: 4) |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| vector_store | ElasticsearchStore | Elasticsearch vector store instance |
| search_results | List[Data] | Results of similarity search |

## FAISS

This component creates a FAISS Vector Store with search capabilities.
For more information, see the [FAISS documentation](https://faiss.ai/index.html).

### Inputs

| Name                      | Type          | Description                                      |
|---------------------------|---------------|--------------------------------------------------|
| index_name                 | String        | The name of the FAISS index. Default: "langflow_index". |
| persist_directory          | String        | Path to save the FAISS index. It will be relative to where Langflow is running. |
| search_query               | String        | The query to search for in the vector store.     |
| ingest_data                | Data          | The data to ingest into the vector store (list of Data objects or documents). |
| allow_dangerous_deserialization | Boolean  | Set to True to allow loading pickle files from untrusted sources. Default: True (advanced). |
| embedding                  | Embeddings    | The embedding function to use for the vector store. |
| number_of_results          | Integer       | Number of results to return from the search. Default: 4 (advanced). |

### Outputs

| Name           | Type                   | Description                    |
|----------------|------------------------|--------------------------------|
| vector_store   | FAISS                  | A FAISS vector store instance configured with the specified parameters. |

## Graph RAG

This component performs Graph RAG (Retrieval Augmented Generation) traversal in a vector store, enabling graph-based document retrieval.
For more information, see the [Graph RAG documentation](https://datastax.github.io/graph-rag/).

For an example flow, see the **Graph RAG** template.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| embedding_model | Embedding Model | Specify the embedding model. This is not required for collections embedded with [Astra vectorize](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html). |
| vector_store | Vector Store Connection | Connection to the vector store. |
| edge_definition | Edge Definition | Edge definition for the graph traversal. For more information, see the [GraphRAG documentation](https://datastax.github.io/graph-rag/reference/graph_retriever/edges/). |
| strategy | Traversal Strategies | The strategy to use for graph traversal. Strategy options are dynamically loaded from available strategies. |
| search_query | Search Query | The query to search for in the vector store. |
| graphrag_strategy_kwargs | Strategy Parameters | Optional dictionary of additional parameters for the retrieval strategy. For more information, see the [strategy documentation](https://datastax.github.io/graph-rag/reference/graph_retriever/strategies/). |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| search_results | List[Data] | Results of the graph-based document retrieval as a list of [Data](/concepts-objects#data-object) objects. |

## Hyper-Converged Database (HCD) Vector Store

This component implements a Vector Store using HCD.

To use the HCD vector store, add your deployment's collection name, username, password, and HCD Data API endpoint.
The endpoint must be formatted like `http[s]://**DOMAIN_NAME** or **IP_ADDRESS**[:port]`, for example, `http://192.0.2.250:8181`.

Replace **DOMAIN_NAME** or **IP_ADDRESS** with the domain name or IP address of your HCD Data API connection.

To use the HCD vector store for embeddings ingestion, connect it to an embeddings model and a file loader:

![HCD vector store embeddings ingestion](/img/component-hcd-example-flow.png)

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| collection_name | Collection Name | The name of the collection within HCD where the vectors will be stored (required) |
| username | HCD Username | Authentication username for accessing HCD (default: "hcd-superuser", required) |
| password | HCD Password | Authentication password for accessing HCD (required) |
| api_endpoint | HCD API Endpoint | API endpoint URL for the HCD service (required) |
| search_input | Search Input | Query string for similarity search |
| ingest_data | Ingest Data | Data to be ingested into the vector store |
| namespace | Namespace | Optional namespace within HCD to use for the collection (default: "default_namespace") |
| ca_certificate | CA Certificate | Optional CA certificate for TLS connections to HCD |
| metric | Metric | Optional distance metric for vector comparisons (options: "cosine", "dot_product", "euclidean") |
| batch_size | Batch Size | Optional number of data to process in a single batch |
| bulk_insert_batch_concurrency | Bulk Insert Batch Concurrency | Optional concurrency level for bulk insert operations |
| bulk_insert_overwrite_concurrency | Bulk Insert Overwrite Concurrency | Optional concurrency level for bulk insert operations that overwrite existing data |
| bulk_delete_concurrency | Bulk Delete Concurrency | Optional concurrency level for bulk delete operations |
| setup_mode | Setup Mode | Configuration mode for setting up the vector store (options: "Sync", "Async", "Off", default: "Sync") |
| pre_delete_collection | Pre Delete Collection | Boolean flag to determine whether to delete the collection before creating a new one |
| metadata_indexing_include | Metadata Indexing Include | Optional list of metadata fields to include in the indexing |
| embedding | Embedding or Astra Vectorize | Allows either an embedding model or an Astra Vectorize configuration |
| metadata_indexing_exclude | Metadata Indexing Exclude | Optional list of metadata fields to exclude from the indexing |
| collection_indexing_policy | Collection Indexing Policy | Optional dictionary defining the indexing policy for the collection |
| number_of_results | Number of Results | Number of results to return in similarity search (default: 4) |
| search_type | Search Type | Search type to use (options: "Similarity", "Similarity with score threshold", "MMR (Max Marginal Relevance)", default: "Similarity") |
| search_score_threshold | Search Score Threshold | Minimum similarity score threshold for search results (default: 0) |
| search_filter | Search Metadata Filter | Optional dictionary of filters to apply to the search query |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | An HCD vector store instance The results of the similarity search as a list of `Data` objects.|
| search_results | Search Results | The results of the similarity search as a list of `Data` objects. |

## Milvus

This component creates a Milvus Vector Store with search capabilities.
For more information, see the [Milvus documentation](https://milvus.io/docs).

### Inputs

| Name                    | Type          | Description                                      |
|-------------------------|---------------|--------------------------------------------------|
| collection_name          | String        | Name of the Milvus collection                    |
| collection_description   | String        | Description of the Milvus collection             |
| uri                      | String        | Connection URI for Milvus                        |
| password                 | SecretString  | Password for Milvus                              |
| username                 | SecretString  | Username for Milvus                              |
| batch_size               | Integer       | Number of data to process in a single batch      |
| search_query             | String        | Query for similarity search                      |
| ingest_data              | Data          | Data to be ingested into the vector store        |
| embedding                | Embeddings    | Embedding function to use                        |
| number_of_results        | Integer       | Number of results to return in search            |
| search_type              | String        | Type of search to perform                        |
| search_score_threshold   | Float         | Minimum similarity score for search results      |
| search_filter            | Dict          | Metadata filters for search query                |
| setup_mode               | String        | Configuration mode for setting up the vector store |
| vector_dimensions        | Integer       | Number of dimensions of the vectors              |
| pre_delete_collection    | Boolean       | Whether to delete the collection before creating a new one |

### Outputs

| Name           | Type                   | Description                    |
|----------------|------------------------|--------------------------------|
| vector_store   | Milvus                 | A Milvus vector store instance configured with the specified parameters. |

## MongoDB Atlas

This component creates a MongoDB Atlas Vector Store with search capabilities.
For more information, see the [MongoDB Atlas documentation](https://www.mongodb.com/docs/atlas/atlas-vector-search/tutorials/vector-search-quick-start/).

### Inputs

| Name                      | Type         | Description                               |
| ------------------------- | ------------ | ----------------------------------------- |
| mongodb_atlas_cluster_uri | SecretString | The connection URI for your MongoDB Atlas cluster (required) |
| enable_mtls               | Boolean      | Enable mutual TLS authentication (default: false) |
| mongodb_atlas_client_cert | SecretString | Client certificate combined with private key for mTLS authentication (required if mTLS is enabled) |
| db_name                   | String       | The name of the database to use (required) |
| collection_name           | String       | The name of the collection to use (required) |
| index_name                | String       | The name of the Atlas Search index, it should be a Vector Search (required) |
| insert_mode               | String       | How to insert new documents into the collection (options: "append", "overwrite", default: "append") |
| embedding                 | Embeddings   | The embedding model to use |
| number_of_results         | Integer      | Number of results to return in similarity search (default: 4) |
| index_field               | String       | The field to index (default: "embedding") |
| filter_field              | String       | The field to filter the index |
| number_dimensions         | Integer      | Embedding context length (default: 1536) |
| similarity                | String       | The method used to measure similarity between vectors (options: "cosine", "euclidean", "dotProduct", default: "cosine") |
| quantization              | String       | Quantization reduces memory costs by converting 32-bit floats to smaller data types (options: "scalar", "binary") |

### Outputs

| Name          | Type                   | Description                               |
| ------------- | ---------------------- | ----------------------------------------- |
| vector_store  | MongoDBAtlasVectorSearch| MongoDB Atlas vector store instance       |
| search_results| List[Data]             | Results of similarity search              |

## Opensearch

This component creates an Opensearch vector store with search capabilities
For more information, see [Opensearch documentation](https://opensearch.org/platform/search/vector-database.html).

### Inputs

| Name                   | Type         | Description                                                                                                            |
|------------------------|--------------|------------------------------------------------------------------------------------------------------------------------|
| opensearch_url         | String       | URL for OpenSearch cluster (e.g. https://192.168.1.1:9200)                                                             |
| index_name             | String       | The index name where the vectors will be stored in OpenSearch cluster                                                  |
| search_input           | String       | Enter a search query. Leave empty to retrieve all documents or if hybrid search is being used                          |
| ingest_data            | Data         | Data to be ingested into the vector store                                                                              |
| embedding              | Embeddings   | Embedding function to use                                                                                              |
| search_type            | String       | Valid values are "similarity", "similarity_score_threshold", "mmr"                                                     |
| number_of_results      | Integer      | Number of results to return in search                                                                                  |
| search_score_threshold | Float        | Minimum similarity score threshold for search results                                                                  |
| username               | String       | username for the opensource cluster                                                                                    |
| password               | SecretString | password for the opensource cluster                                                                                    |
| use_ssl                | Boolean      | Use SSL                                                                                                                |
| verify_certs           | Boolean      | Verify certificates                                                                                                    |
| hybrid_search_query    | String       | Provide a custom hybrid search query in JSON format. This allows you to combine vector similarity and keyword matching |

### Outputs

| Name          | Type                   | Description                                 |
| ------------- |------------------------|---------------------------------------------|
| vector_store  | OpenSearchVectorSearch | OpenSearch vector store instance            |
| search_results| List[Data]             | Results of similarity search                |

## PGVector

This component creates a PGVector Vector Store with search capabilities.
For more information, see the [PGVector documentation](https://github.com/pgvector/pgvector).

### Inputs

| Name            | Type         | Description                               |
| --------------- | ------------ | ----------------------------------------- |
| pg_server_url   | SecretString | PostgreSQL server connection string       |
| collection_name | String       | Table name for the vector store           |
| search_query    | String       | Query for similarity search               |
| ingest_data     | Data         | Data to be ingested into the vector store |
| embedding       | Embeddings   | Embedding function to use                 |
| number_of_results | Integer    | Number of results to return in search     |

### Outputs

| Name          | Type        | Description                               |
| ------------- | ----------- | ----------------------------------------- |
| vector_store  | PGVector    | PGVector vector store instance            |
| search_results| List[Data]  | Results of similarity search              |


## Pinecone

This component creates a Pinecone Vector Store with search capabilities.
For more information, see the [Pinecone documentation](https://docs.pinecone.io/home).

### Inputs

| Name              | Type         | Description                               |
| ----------------- | ------------ | ----------------------------------------- |
| index_name        | String       | Name of the Pinecone index                |
| namespace         | String       | Namespace for the index                   |
| distance_strategy | String       | Strategy for calculating distance between vectors |
| pinecone_api_key  | SecretString | API key for Pinecone                      |
| text_key          | String       | Key in the record to use as text          |
| search_query      | String       | Query for similarity search               |
| ingest_data       | Data         | Data to be ingested into the vector store |
| embedding         | Embeddings   | Embedding function to use                 |
| number_of_results | Integer      | Number of results to return in search     |

### Outputs

| Name          | Type       | Description                               |
| ------------- | ---------- | ----------------------------------------- |
| vector_store  | Pinecone   | Pinecone vector store instance            |
| search_results| List[Data] | Results of similarity search              |


## Qdrant

This component creates a Qdrant Vector Store with search capabilities.
For more information, see the [Qdrant documentation](https://qdrant.tech/documentation/).

### Inputs

| Name                 | Type         | Description                               |
| -------------------- | ------------ | ----------------------------------------- |
| collection_name       | String       | Name of the Qdrant collection             |
| host                 | String       | Qdrant server host                        |
| port                 | Integer      | Qdrant server port                        |
| grpc_port            | Integer      | Qdrant gRPC port                          |
| api_key              | SecretString | API key for Qdrant                        |
| prefix               | String       | Prefix for Qdrant                         |
| timeout              | Integer      | Timeout for Qdrant operations             |
| path                 | String       | Path for Qdrant                           |
| url                  | String       | URL for Qdrant                            |
| distance_func        | String       | Distance function for vector similarity   |
| content_payload_key  | String       | Key for content payload                   |
| metadata_payload_key | String       | Key for metadata payload                  |
| search_query         | String       | Query for similarity search               |
| ingest_data          | Data         | Data to be ingested into the vector store |
| embedding            | Embeddings   | Embedding function to use                 |
| number_of_results    | Integer      | Number of results to return in search     |

### Outputs

| Name          | Type     | Description                               |
| ------------- | -------- | ----------------------------------------- |
| vector_store  | Qdrant   | Qdrant vector store instance              |
| search_results| List[Data] | Results of similarity search            |


## Redis

This component creates a Redis Vector Store with search capabilities.
For more information, see the [Redis documentation](https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/vectors/).

### Inputs

| Name              | Type         | Description                               |
| ----------------- | ------------ | ----------------------------------------- |
| redis_server_url  | SecretString | Redis server connection string            |
| redis_index_name  | String       | Name of the Redis index                   |
| code              | String       | Custom code for Redis (advanced)          |
| schema            | String       | Schema for Redis index                    |
| search_query      | String       | Query for similarity search               |
| ingest_data       | Data         | Data to be ingested into the vector store |
| number_of_results | Integer      | Number of results to return in search     |
| embedding         | Embeddings   | Embedding function to use                 |

### Outputs

| Name          | Type     | Description                               |
| ------------- | -------- | ----------------------------------------- |
| vector_store  | Redis    | Redis vector store instance               |
| search_results| List[Data]| Results of similarity search             |


## Supabase

This component creates a connection to a Supabase Vector Store with search capabilities.
For more information, see the [Supabase documentation](https://supabase.com/docs/guides/ai).

### Inputs

| Name                | Type         | Description                               |
| ------------------- | ------------ | ----------------------------------------- |
| supabase_url        | String       | URL of the Supabase instance              |
| supabase_service_key| SecretString | Service key for Supabase authentication   |
| table_name          | String       | Name of the table in Supabase             |
| query_name          | String       | Name of the query to use                  |
| search_query        | String       | Query for similarity search               |
| ingest_data         | Data         | Data to be ingested into the vector store |
| embedding           | Embeddings   | Embedding function to use                 |
| number_of_results   | Integer      | Number of results to return in search     |

### Outputs

| Name          | Type               | Description                               |
| ------------- | ------------------ | ----------------------------------------- |
| vector_store  | SupabaseVectorStore | Supabase vector store instance            |
| search_results| List[Data]          | Results of similarity search              |


## Upstash

This component creates an Upstash Vector Store with search capabilities.
For more information, see the [Upstash documentation](https://upstash.com/docs/introduction).

### Inputs

| Name            | Type         | Description                               |
| --------------- | ------------ | ----------------------------------------- |
| index_url       | String       | The URL of the Upstash index              |
| index_token     | SecretString | The token for the Upstash index           |
| text_key        | String       | The key in the record to use as text      |
| namespace       | String       | Namespace for the index                   |
| search_query    | String       | Query for similarity search               |
| metadata_filter | String       | Filters documents by metadata             |
| ingest_data     | Data         | Data to be ingested into the vector store |
| embedding       | Embeddings   | Embedding function to use (optional)      |
| number_of_results | Integer    | Number of results to return in search     |

### Outputs

| Name          | Type             | Description                               |
| ------------- | ---------------- | ----------------------------------------- |
| vector_store  | UpstashVectorStore| Upstash vector store instance             |
| search_results| List[Data]        | Results of similarity search              |


## Vectara

This component creates a Vectara Vector Store with search capabilities.
For more information, see the [Vectara documentation](https://docs.vectara.com/docs/).

### Inputs

| Name             | Type         | Description                               |
| ---------------- | ------------ | ----------------------------------------- |
| vectara_customer_id | String     | Vectara customer ID                       |
| vectara_corpus_id   | String     | Vectara corpus ID                         |
| vectara_api_key   | SecretString | Vectara API key                           |
| embedding         | Embeddings   | Embedding function to use (optional)      |
| ingest_data       | List[Document/Data] | Data to be ingested into the vector store |
| search_query      | String       | Query for similarity search               |
| number_of_results | Integer      | Number of results to return in search     |

### Outputs

| Name          | Type              | Description                               |
| ------------- | ----------------- | ----------------------------------------- |
| vector_store  | VectaraVectorStore | Vectara vector store instance             |
| search_results| List[Data]         | Results of similarity search              |

## Vectara Search

This component searches a Vectara Vector Store for documents based on the provided input.
For more information, see the [Vectara documentation](https://docs.vectara.com/docs/).

### Inputs

| Name                | Type         | Description                               |
|---------------------|--------------|-------------------------------------------|
| search_type         | String       | Type of search, such as "Similarity" or "MMR" |
| input_value         | String       | Search query                              |
| vectara_customer_id | String       | Vectara customer ID                       |
| vectara_corpus_id   | String       | Vectara corpus ID                         |
| vectara_api_key     | SecretString | Vectara API key                           |
| files_url           | List[String] | Optional URLs for file initialization     |

### Outputs

| Name           | Type       | Description                |
|----------------|------------|----------------------------|
| search_results | List[Data] | Results of similarity search |

## Weaviate

This component facilitates a Weaviate Vector Store setup, optimizing text and document indexing and retrieval.
For more information, see the [Weaviate Documentation](https://weaviate.io/developers/weaviate).

### Inputs

| Name          | Type         | Description                               |
|---------------|--------------|-------------------------------------------|
| weaviate_url  | String       | Default instance URL                      |
| search_by_text| Boolean      | Indicates whether to search by text       |
| api_key       | SecretString | Optional API key for authentication       |
| index_name    | String       | Optional index name                       |
| text_key      | String       | Default text extraction key               |
| input         | Document     | Document or record                        |
| embedding     | Embeddings   | Model used                                |
| attributes    | List[String] | Optional additional attributes            |

### Outputs

| Name         | Type             | Description                   |
|--------------|------------------|-------------------------------|
| vector_store | WeaviateVectorStore | Weaviate vector store instance |

## Weaviate Search

This component searches a Weaviate Vector Store for documents similar to the input.
For more information, see the [Weaviate Documentation](https://weaviate.io/developers/weaviate).

### Inputs

| Name          | Type         | Description                               |
|---------------|--------------|-------------------------------------------|
| search_type   | String       | Type of search, such as "Similarity" or "MMR" |
| input_value   | String       | Search query                              |
| weaviate_url  | String       | Default instance URL                      |
| search_by_text| Boolean      | Indicates whether to search by text       |
| api_key       | SecretString | Optional API key for authentication       |
| index_name    | String       | Optional index name                       |
| text_key      | String       | Default text extraction key               |
| embedding     | Embeddings   | Model used                                |
| attributes    | List[String] | Optional additional attributes            |

### Outputs

| Name           | Type       | Description                |
|----------------|------------|----------------------------|
| search_results | List[Data] | Results of similarity search |



