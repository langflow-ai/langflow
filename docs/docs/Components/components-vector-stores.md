---
title: Vector stores
slug: /components-vector-stores
---

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
| collection_name | Collection Name | The name of the collection within Astra DB where the vectors will be stored (required) |
| token | Astra DB Application Token | Authentication token for accessing Astra DB (required) |
| api_endpoint | API Endpoint | API endpoint URL for the Astra DB service (required) |
| search_input | Search Input | Query string for similarity search |
| ingest_data | Ingest Data | Data to be ingested into the vector store |
| namespace | Namespace | Optional namespace within Astra DB to use for the collection |
| embedding_choice | Embedding Model or Astra Vectorize | Determines whether to use an Embedding Model or Astra Vectorize for the collection |
| embedding | Embedding Model | Allows an embedding model configuration (when using Embedding Model) |
| provider | Vectorize Provider | Provider for Astra Vectorize (when using Astra Vectorize) |
| metric | Metric | Optional distance metric for vector comparisons |
| batch_size | Batch Size | Optional number of data to process in a single batch |
| setup_mode | Setup Mode | Configuration mode for setting up the vector store (options: "Sync", "Async", "Off", default: "Sync") |
| pre_delete_collection | Pre Delete Collection | Boolean flag to determine whether to delete the collection before creating a new one |
| number_of_results | Number of Results | Number of results to return in similarity search (default: 4) |
| search_type | Search Type | Search type to use (options: "Similarity", "Similarity with score threshold", "MMR (Max Marginal Relevance)") |
| search_score_threshold | Search Score Threshold | Minimum similarity score threshold for search results |
| search_filter | Search Metadata Filter | Optional dictionary of filters to apply to the search query |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| vector_store | Vector Store | Astra DB vector store instance configured with the specified parameters. |
| search_results | Search Results | The results of the similarity search as a list of `Data` objects. |


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

## Hyper-Converged Database (HCD) Vector Store

This component implements a Vector Store using HCD.

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

| Name                     | Type         | Description                               |
| ------------------------ | ------------ | ----------------------------------------- |
| mongodb_atlas_cluster_uri | SecretString | MongoDB Atlas Cluster URI                 |
| db_name                   | String       | Database name                             |
| collection_name           | String       | Collection name                           |
| index_name                | String       | Index name                                |
| search_query              | String       | Query for similarity search               |
| ingest_data               | Data         | Data to be ingested into the vector store |
| embedding                 | Embeddings   | Embedding function to use                 |
| number_of_results         | Integer      | Number of results to return in search     |

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

## Vectara RAG

This component leverages Vectara's Retrieval Augmented Generation (RAG) capabilities to search and summarize documents based on the provided input. For more information, see the [Vectara documentation](https://docs.vectara.com/docs/).

### Inputs

| Name                  | Type         | Description                                                |
|-----------------------|--------------|------------------------------------------------------------|
| vectara_customer_id   | String       | Vectara customer ID                                        |
| vectara_corpus_id     | String       | Vectara corpus ID                                          |
| vectara_api_key       | SecretString | Vectara API key                                            |
| search_query          | String       | The query to receive an answer on                          |
| lexical_interpolation | Float        | Hybrid search factor (0.005 to 0.1)                        |
| filter                | String       | Metadata filters to narrow the search                      |
| reranker              | String       | Reranker type (mmr, rerank_multilingual_v1, none)          |
| reranker_k            | Integer      | Number of results to rerank (1 to 100)                     |
| diversity_bias        | Float        | Diversity bias for MMR reranker (0 to 1)                   |
| max_results           | Integer      | Maximum number of search results to summarize (1 to 100)   |
| response_lang         | String       | Language code for the response (for example, "eng", "auto")       |
| prompt                | String       | Prompt name for summarization                              |

### Outputs

| Name   | Type    | Description           |
|--------|---------|-----------------------|
| answer | Message | Generated RAG response|

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



