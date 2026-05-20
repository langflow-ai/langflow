# IBM DB2 Vector Store Component - Developer Guidelines

## Overview

This document provides comprehensive guidelines for understanding, testing, and working with the IBM DB2 Vector Store component in Langflow.

## Component Architecture

### Files Structure

```
src/lfx/src/lfx/components/ibm/
├── db2_vector.py          # Main vector store component
├── db2vs.py               # DB2 vector store implementation
├── db2_security.py        # Security validation utilities
└── __init__.py

src/backend/tests/unit/components/ibm/
├── test_db2_vector.py     # Component integration tests
├── test_db2vs.py          # DB2VS class unit tests
├── test_db2_security.py   # Security validation tests
└── __init__.py

src/frontend/src/icons/IBM/db2/
└── DB2.jsx                # Component icon
```

### Component Hierarchy

```
DB2VectorStoreComponent (db2_vector.py)
    ↓ uses
DB2VS (db2vs.py) - LangChain VectorStore implementation
    ↓ uses
Security Validators (db2_security.py)
```

## Key Features

### 1. Vector Store Operations
- **Add Documents**: Ingest Data objects with embeddings
- **Similarity Search**: Find similar documents using vector similarity
- **MMR Search**: Maximum Marginal Relevance search for diverse results
- **Similarity Score Threshold**: Filter results by similarity score
- **Metadata Filtering**: Filter documents by metadata attributes

### 2. Security Features
- Database name validation (alphanumeric, underscore, max 128 chars)
- Hostname validation (FQDN or IP address)
- Port validation (1-65535)
- SQL identifier validation (prevents injection)
- Credential redaction in error messages

### 3. Data Ingestion
- Accepts `Data` objects only (Langflow standard)
- Automatic metadata filtering for complex types
- Duplicate detection (optional)
- Batch processing support

## Testing

### Running Tests

```bash
# Run all DB2 component tests
cd src/backend
uv run pytest tests/unit/components/ibm/ -v

# Run specific test file
uv run pytest tests/unit/components/ibm/test_db2_vector.py -v

# Run specific test
uv run pytest tests/unit/components/ibm/test_db2_vector.py::test_similarity_search -v

# Run with coverage
uv run pytest tests/unit/components/ibm/ --cov=lfx.components.ibm --cov-report=html
```

### Test Coverage Summary

#### test_db2_vector.py (20 tests)
- Component metadata validation
- Build vector store functionality
- Search operations (similarity, MMR, similarity_score_threshold)
- Data ingestion with various input types
- Duplicate handling
- Metadata filtering with complex data
- Error handling

#### test_db2vs.py (12 tests)
- DB2VS class initialization
- Table existence checking
- Distance function selection
- Add texts functionality
- Delete operations
- Dimension validation

#### test_db2_security.py (9 tests)
- Database name validation
- Hostname validation
- Port validation
- SQL identifier validation
- Error message sanitization

**Total: 41 tests (38 passing, 3 skipped)**

### Test Patterns

#### 1. Component Testing Pattern
```python
def test_component_feature():
    # Arrange: Create component with mocked dependencies
    component = DB2VectorStoreComponent()
    component.embedding = MagicMock()

    # Act: Execute component method
    result = component.build_vector_store()

    # Assert: Verify behavior
    assert result is not None
```

#### 2. Integration Testing Pattern
```python
@patch("lfx.components.ibm.db2_vector.DB2VS")
def test_integration_feature(mock_db2vs):
    # Setup mocks
    mock_instance = MagicMock()
    mock_db2vs.return_value = mock_instance

    # Test integration
    component = DB2VectorStoreComponent()
    component.build_vector_store()

    # Verify integration
    mock_db2vs.assert_called_once()
```

## Component Usage

### Basic Usage

```python
from lfx.components.ibm import DB2VectorStoreComponent
from langflow.schema import Data

# Initialize component
db2_component = DB2VectorStoreComponent()

# Configure connection
db2_component.database = "TESTDB"
db2_component.hostname = "localhost"
db2_component.port = 50000
db2_component.username = "db2user"
db2_component.password = "password"
db2_component.collection_name = "my_vectors"

# Set embedding model
db2_component.embedding = embedding_model

# Ingest data
data = [
    Data(text="Document 1", metadata={"source": "file1.txt"}),
    Data(text="Document 2", metadata={"source": "file2.txt"})
]
db2_component.ingest_data = data

# Build vector store
vector_store = db2_component.build_vector_store()

# Search
db2_component.search_query = "search term"
results = db2_component.search_documents()
```

### Search Types

#### 1. Similarity Search
```python
db2_component.search_type = "Similarity"
db2_component.number_of_results = 5
results = db2_component.search_documents()
```

#### 2. MMR Search
```python
db2_component.search_type = "MMR"
db2_component.number_of_results = 5
results = db2_component.search_documents()
```

#### 3. Similarity Score Threshold
```python
db2_component.search_type = "Similarity score threshold"
db2_component.search_score_threshold = 0.7
results = db2_component.search_documents()
```

## Development Guidelines

### Adding New Features

1. **Update Component Class** (`db2_vector.py`)
   - Add input fields if needed
   - Implement feature logic
   - Update docstrings

2. **Add Tests** (`test_db2_vector.py`)
   - Unit tests for new methods
   - Integration tests for workflows
   - Edge case coverage

3. **Update Security** (if needed)
   - Add validators in `db2_security.py`
   - Add tests in `test_db2_security.py`

### Code Style

- Follow Langflow component patterns
- Use type hints
- Add comprehensive docstrings
- Handle errors gracefully
- Log important operations

### Testing Requirements

- All new features must have tests
- Maintain >80% code coverage
- Test both success and failure paths
- Mock external dependencies (DB2, embeddings)
- Use fixtures for common test data

## Common Issues & Solutions

### Issue 1: Import Errors
**Problem**: `ModuleNotFoundError: No module named 'ibm_db'`

**Solution**:
```bash
pip install ibm-db ibm-db-dbi
```

### Issue 2: Connection Failures
**Problem**: Cannot connect to DB2 database

**Solution**:
- Verify hostname and port
- Check credentials
- Ensure DB2 server is running
- Check firewall rules

### Issue 3: Test Failures
**Problem**: Tests fail with "No module named 'lfx'"

**Solution**:
```bash
cd src/lfx
uv sync
uv run pytest
```

### Issue 4: Dimension Mismatch
**Problem**: `ValueError: Embedding dimension mismatch`

**Solution**:
- Ensure embedding model dimension matches table dimension
- Drop and recreate table if dimension changed
- Use consistent embedding model

## Performance Considerations

### Indexing
- DB2 automatically creates vector indexes
- Index creation happens on first insert
- Large datasets may take time to index

### Batch Operations
- Use batch inserts for large datasets
- Recommended batch size: 100-1000 documents
- Monitor memory usage

### Search Optimization
- Use appropriate search type for use case
- Limit number of results
- Use metadata filtering to reduce search space

## Security Best Practices

1. **Credentials Management**
   - Never hardcode credentials
   - Use environment variables or secrets management
   - Rotate credentials regularly

2. **Input Validation**
   - All inputs are validated before use
   - SQL injection prevention built-in
   - Error messages sanitize sensitive data

3. **Connection Security**
   - Use SSL/TLS for production
   - Implement connection pooling
   - Set appropriate timeouts

## Troubleshooting

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Component Status
```python
print(component.status)  # Shows current operation status
```

### Verify Vector Store
```python
vector_store = component.build_vector_store()
print(f"Collection: {vector_store.collection_name}")
print(f"Dimension: {vector_store.dimension}")
```

## Contributing

### Before Submitting PR

1. Run all tests: `make unit_tests`
2. Check code style: `make format_backend && make lint`
3. Update documentation if needed
4. Add tests for new features
5. Ensure all tests pass

### PR Guidelines

- Follow semantic commit conventions
- Reference related issues
- Provide clear description
- Include test results
- Update CHANGELOG if applicable

## Resources

- [IBM DB2 Documentation](https://www.ibm.com/docs/en/db2)
- [LangChain VectorStore Guide](https://python.langchain.com/docs/modules/data_connection/vectorstores/)
- [Langflow Component Development](https://docs.langflow.org/)

## Support

For issues or questions:
1. Check this documentation
2. Review existing tests for examples
3. Check Langflow documentation
4. Open an issue on GitHub

---

**Last Updated**: 2026-05-20
**Component Version**: 1.0.0
**Langflow Version**: Compatible with 1.x