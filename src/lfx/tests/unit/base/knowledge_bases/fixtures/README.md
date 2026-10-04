# Local Chroma reader fixtures

`chroma-1.5.9-local.tar.gz` was produced by the real Chroma 1.5.9 SDK using
`tools/chroma_migration_helper/create_fixture.py`. It contains synthetic SQLite
metadata, persistent HNSW indexes, pending additions, updates and deletes, and
SDK-exported expectations for L2, cosine, inner product and an empty collection.
The embedding function is disabled. No models, credentials or user data are
included. One stored embedding-function configuration is deliberately unsafe
and must remain inert. The application reader never imports or executes it.

The archive timestamps and ownership are normalized. Tests extract regular files
only into a private test directory. They compare the reader output with the
independent SDK expectations. Pending cosine log vectors preserve the original
float32 values, avoiding the small round-trip normalization error in Chroma get().

`chroma-0.5.23-local.tar.gz` was produced by Python Chroma 0.5.23 using the
same 240-record operations for all three metrics and an empty collection.
It uses the historical `hnsw:space` collection metadata, Python PersistentData
index metadata and blob checkpoints. Its vectors and metadata were obtained
independently through that SDK's get() before stopping the system.
