# Cassandra & ScyllaDB Integration Tests

This directory contains integration tests verifying **ScyllaDB as a drop-in replacement for Apache Cassandra** in Langflow.

## Overview

These tests demonstrate that:
1. **Zero code changes** needed in Langflow components
2. **Same driver** (`cassandra-driver`) works with both databases
3. **Identical behavior** for all operations
4. **Drop-in compatibility** proven through parametrized tests

## Test Structure

### Parametrized Tests

All tests use pytest's `@pytest.fixture(params=["cassandra", "scylladb"])` to automatically run against both databases:

```python
@pytest.fixture(params=["cassandra", "scylladb"])
def db_config(request):
    """Tests run automatically against both databases"""
    ...
```

This means each test function runs **twice**:
- Once against Cassandra (port 9043)
- Once against ScyllaDB (port 9042)

### Test Files

1. **test_cassandra_vectorstore.py** - CassandraVectorStoreComponent tests
   - Basic connectivity
   - Document ingestion
   - Similarity search
   - Driver compatibility
   - Connection formats

2. **test_cassandra_chat_memory.py** - CassandraChatMemory tests
   - Message storage and retrieval
   - Session isolation
   - Persistence
   - Clear operations

## Prerequisites

### 1. Install Dependencies

```bash
# Install cassio and cassandra-driver
pip install "cassio>=0.1.7"
pip install "cassandra-driver>=3.29.0"

# Or install with langflow extras
pip install "langflow[cassio]"

# For vector store tests, you'll need OpenAI API key
export OPENAI_API_KEY=your_api_key_here
```

### 2. Start Docker Containers

```bash
# Start ScyllaDB (port 9042)
docker run -d \
  --name langflow-scylladb-test \
  -p 9042:9042 \
  scylladb/scylla:2025.1.4 \
  --reactor-backend epoll --smp 1 --memory 1G --overprovisioned 1 --api-address 0.0.0.0

# Start Cassandra (port 9043)
docker run -d \
  --name langflow-cassandra-test \
  -p 9043:9042 \
  -e CASSANDRA_CLUSTER_NAME=TestCluster \
  cassandra:4.1
```

Wait for containers to be healthy (~60 seconds):
```bash
docker ps
# Both should show "Up" status
```

**Note:** No manual database initialization needed - cassio will automatically create keyspaces and tables when tests run.

## Running Tests

### Run All Cassandra Tests

```bash
# From langflow root
pytest src/backend/tests/integration/components/cassandra/ -v
```

### Run Specific Test File

```bash
# Vector store tests only
pytest src/backend/tests/integration/components/cassandra/test_cassandra_vectorstore.py -v

# Chat memory tests only
pytest src/backend/tests/integration/components/cassandra/test_cassandra_chat_memory.py -v
```

### Run Specific Test Function

```bash
# Test only the basic vector store functionality
pytest src/backend/tests/integration/components/cassandra/test_cassandra_vectorstore.py::test_cassandra_vector_store_basic -v
```

### Filter by Database

```bash
# Test only ScyllaDB
pytest src/backend/tests/integration/components/cassandra/ -v -k scylladb

# Test only Cassandra
pytest src/backend/tests/integration/components/cassandra/ -v -k cassandra
```

### Verbose Output with Print Statements

```bash
# See the print statements (e.g., "✓ ScyllaDB: Basic test passed")
pytest src/backend/tests/integration/components/cassandra/ -v -s
```

## Environment Variables

You can override default connection settings:

```bash
# ScyllaDB configuration
export SCYLLADB_HOST=localhost
export SCYLLADB_PORT=9042
export SCYLLADB_KEYSPACE=langflow_test

# Cassandra configuration
export CASSANDRA_HOST=localhost
export CASSANDRA_PORT=9043
export CASSANDRA_KEYSPACE=langflow_test

# OpenAI API key (for vector embedding tests)
export OPENAI_API_KEY=your_key_here
```

## Expected Results

### Success Scenario

When tests pass for **both** databases:
```
test_cassandra_vectorstore.py::test_cassandra_vector_store_basic[cassandra] PASSED
test_cassandra_vectorstore.py::test_cassandra_vector_store_basic[scylladb] PASSED
✓ Cassandra: Basic vector store test passed
✓ ScyllaDB: Basic vector store test passed
```

This proves drop-in compatibility!

### Skip Scenario

If OpenAI API key is not set:
```
test_cassandra_vectorstore.py::test_cassandra_ingest_and_search[cassandra] SKIPPED
test_cassandra_vectorstore.py::test_cassandra_ingest_and_search[scylladb] SKIPPED
```

These tests require embeddings, so they skip gracefully.

### Failure Scenario

If containers aren't running or databases aren't initialized:
```
ERROR: Connection refused
```

Solution: Check containers and run setup script.

## Test Coverage

### CassandraVectorStoreComponent

- ✅ Basic vector store creation
- ✅ Document ingestion
- ✅ Similarity search
- ✅ Multiple connection formats
- ✅ Driver compatibility
- ✅ Keyspace verification

### CassandraChatMemory

- ✅ Connection and session creation
- ✅ Adding and retrieving messages
- ✅ Message persistence
- ✅ Clear operations
- ✅ Multiple session isolation

## Troubleshooting

### Tests fail with "cassandra-driver not installed"

```bash
pip install cassio
# This will install cassandra-driver as a dependency
```

### Tests fail with "Keyspace not found"

This shouldn't happen - cassio creates keyspaces automatically. If it does:
- Ensure containers are running and healthy
- Check cassio is properly installed
- Verify database credentials are correct

### Tests fail with "Connection refused"

1. Check containers are running:
   ```bash
   docker ps
   ```

2. Wait for healthcheck to pass:
   ```bash
   docker logs langflow-scylladb-test
   docker logs langflow-cassandra-test
   ```

3. Verify ports:
   ```bash
   netstat -an | grep 9042
   netstat -an | grep 9043
   ```

### Tests are slow

Vector store tests with embeddings can be slow due to:
- OpenAI API calls
- Embedding generation
- Network latency

Use `-k` to run specific tests:
```bash
pytest src/backend/tests/integration/components/cassandra/ -v -k "driver_compatibility"
```

### One database passes, the other fails

This indicates a **compatibility issue**. Check:
1. Database logs for errors
2. CQL syntax differences
3. Driver version compatibility
4. Feature support (e.g., vector data type)

## Drop-In Compatibility Verification

The key test is `test_cassandra_driver_compatibility`:

```python
def test_cassandra_driver_compatibility(db_config):
    """
    Verifies the same driver library works unchanged with both databases.
    """
    cluster = Cluster([db_config["host"]], port=db_config["port"])
    session = cluster.connect()
    result = session.execute("SELECT release_version FROM system.local")
    ...
```

When this test passes for **both** databases, it proves:
- ✅ Same driver code
- ✅ Same CQL protocol
- ✅ Same connection method
- ✅ Drop-in compatible!

## Performance Comparison

While not the focus of these tests, you can compare execution times:

```bash
pytest src/backend/tests/integration/components/cassandra/ -v --durations=10
```

This shows the 10 slowest tests and their durations for both databases.

## Contributing

When adding new Cassandra components:

1. Add tests to this directory
2. Use the `db_config` parametrized fixture
3. Ensure tests run against both databases
4. Verify identical behavior
5. Document any database-specific quirks

## References

- [ScyllaDB Drop-In Compatibility Template](../../../../SCYLLADB_INTEGRATION_TEMPLATE.md)
- [Cassandra Components Documentation](../../../../../../docs/docs/Components/bundles-cassandra.mdx)
