## Intro
This is the VectorStore for Oracle Database AI Vector Search (Oracle 23ai+).

## Parameters 
DSN: The dsn value can be one of Oracle Database's naming methods as below:
     a. An Oracle Easy Connect string, with the format dbhost:port/service_name
     b. A Connect Descriptor
     c. A TNS Alias mapping to a Connect Descriptor stored in a tnsnames.ora file
    Refer to https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html for more details

Database User: The database schema username

User Password: Database user password

Table: The database table from which you are querying. This is also known as the collection name. The specified table will be automatically created if not exists.

Distance Strategy: The distance function you are using to calculate the similarity among vectors. Valid values are COSINE, EUCLIDEAN and DOT, default is COSINE.

Embeddings: The embedding model for use to embed document(s)


## A manual test flow

### Ingest data

This is step is for data preparation, which simply uploads some text files to the Oracle database using the "File" component. 

Detail flow is as following:

1. Start with (Drag & Drop) the File component and a Fake Embeddings component
2. Connect the "DataFrame" of the File component to the "Ingest Data" of the OracleVS
3. Connect the Fake Embeddings to the "Embedding" control of the OracleVS component
4. Uploads some small txt files in the File component
5. Run the OracleVS component
6. Check the database table and its data. 

It is expected that the specified table is created and the data (txt files) is loaded to the table successfully. Certainly, you can replace the Fake Embedding component to a real Embedding component of your choice. 

### Query data

A very quick & simple test flow is as following:

1. Start with a Chat Input component and a Fake Embeddings component
2. Connect the Chat Input component to the "Search Query" control of the OracleVS component
3. Connect the Fake Embeddings to the "Embedding" control of the OracleVS component
4. Connect the "Search Results" of the OracleVS component to the Chat Output component
5. Run Playground.

Certainly, you can replace the Fake Embedding component to a real Embedding component of your choice. 
