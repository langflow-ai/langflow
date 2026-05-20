# IBM DB2 Vector Search Integration
## Technical Documentation

**Version:** 1.0
**Date:** May 2026
**Platform:** Langflow AI Workflow Builder

---

## 1. Overview

### 1.1 Introduction

The IBM DB2 Vector Search integration enables enterprise-grade semantic search and Retrieval-Augmented Generation (RAG) capabilities within Langflow, leveraging IBM's robust database infrastructure for AI-powered applications.

### 1.2 Key Features

- ✅ **Vector Storage**: High-dimensional embedding storage with automatic table management
- ✅ **Semantic Search**: Similarity search with multiple distance metrics (Cosine, Euclidean, Dot Product)
- ✅ **Security-First**: Comprehensive SQL injection prevention and input validation
- ✅ **Multi-Format Support**: Ingest data from CSV, JSON, DataFrame, and more
- ✅ **Production-Ready**: Connection pooling, error handling, and monitoring

### 1.3 Use Cases

| Use Case | Description |
|----------|-------------|
| **RAG Applications** | Retrieve relevant context for LLM prompts |
| **Semantic Search** | Find documents by meaning, not keywords |
| **Document Classification** | Organize large document collections |
| **Recommendation Systems** | Suggest similar items based on embeddings |

---

## 2. Architecture

### 2.1 System Architecture

```mermaid
graph TB
    subgraph "Langflow Frontend"
        A[DB2 Vector Store Component]
        B[DB2 SQL Component]
        C[Embedding Models]
    end

    subgraph "Langflow Backend"
        D[Component Layer]
        E[DB2VS Core Module]
        F[Security Layer]
    end

    subgraph "IBM DB2 Database"
        G[(Vector Tables)]
        H[ID, TEXT, METADATA, EMBEDDING]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H

    style A fill:#e1f5ff
    style B fill:#e1f5ff
    style C fill:#e1f5ff
    style E fill:#fff4e1
    style F fill:#ffe1e1
    style G fill:#e1ffe1
```

### 2.2 Component Architecture

```mermaid
classDiagram
    class DB2VectorStoreComponent {
        +database: str
        +hostname: str
        +embedding: Embeddings
        +collection_name: str
        +build_vector_store() DB2VS
        +search_documents() List~Data~
        +perform_search() DataFrame
    }

    class DB2VS {
        -client: Connection
        -embedding_function: Embeddings
        -table_name: str
        -distance_strategy: DistanceStrategy
        +add_texts(texts, metadata, ids)
        +similarity_search(query, k, filter)
        +max_marginal_relevance_search()
        +delete(ids)
    }

    class SecurityModule {
        +validate_identifier(id, type)
        +validate_hostname(hostname)
        +sanitize_sql_string(value)
        +validate_sql_query_safety(query)
        +create_safe_error_message(error)
    }

    DB2VectorStoreComponent --> DB2VS : creates
    DB2VS --> SecurityModule : uses
```

### 2.3 Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Component
    participant E as Embedding
    participant V as DB2VS
    participant D as DB2 Database

    U->>C: Ingest Data (CSV/JSON/DataFrame)
    C->>C: Parse & Extract Metadata
    C->>E: Generate Embeddings
    E-->>C: Vector Embeddings
    C->>V: add_documents(docs, embeddings)
    V->>V: Validate & Sanitize
    V->>D: INSERT INTO table
    D-->>V: Success
    V-->>C: Document Count
    C-->>U: Ingestion Complete

    U->>C: Search Query
    C->>E: Generate Query Embedding
    E-->>C: Query Vector
    C->>V: similarity_search(embedding, k)
    V->>D: SELECT with Distance Calculation
    D-->>V: Top K Results
    V-->>C: Documents with Scores
    C-->>U: Search Results
```

---

## 3. Security Architecture

### 3.1 Defense-in-Depth Security

```mermaid
graph TD
    A[User Input] --> B[Layer 1: Input Validation]
    B --> C[Layer 2: SQL Injection Prevention]
    C --> D[Layer 3: String Sanitization]
    D --> E[Layer 4: Error Sanitization]
    E --> F[Safe Database Operation]

    B --> B1[Identifier Validation]
    B --> B2[Hostname Validation]
    B --> B3[Port Validation]

    C --> C1[Operation Whitelisting]
    C --> C2[Multi-Statement Detection]
    C --> C3[Comment Blocking]

    D --> D1[Quote Escaping]
    D --> D2[Special Character Handling]

    E --> E1[Credential Redaction]
    E --> E2[Generic Error Messages]

    style B fill:#ffe1e1
    style C fill:#ffe1e1
    style D fill:#ffe1e1
    style E fill:#ffe1e1
    style F fill:#e1ffe1
```

### 3.2 Security Features

| Feature | Implementation | Protection Against |
|---------|----------------|---------------------|
| **Identifier Validation** | Regex pattern matching, reserved keyword blocking | SQL injection via table/column names |
| **Query Safety** | Operation whitelisting, multi-statement detection | Malicious query execution |
| **String Sanitization** | Single quote escaping (SQL standard) | String-based injection |
| **Error Sanitization** | Generic error messages, credential redaction | Information disclosure |
| **Read-Only Mode** | SELECT-only enforcement | Unauthorized data modification |
| **Query Timeout** | Configurable timeout (1-300s) | Resource exhaustion |

### 3.3 SQL Injection Prevention

```python
# ✅ SAFE: Validated identifier
validate_identifier("my_table")  # Returns: "my_table"

# ❌ BLOCKED: SQL injection attempt
validate_identifier("table; DROP TABLE users")
# Raises: ValueError("Invalid identifier")

# ❌ BLOCKED: Reserved keyword
validate_identifier("SELECT")
# Raises: ValueError("reserved SQL keyword")

# ✅ SAFE: Sanitized string
sanitize_sql_string("it's working")  # Returns: "it''s working"

# ✅ SAFE: Query validation
validate_sql_query_safety(
    "SELECT * FROM users",
    allowed_operations={"SELECT"}
)  # Passes

# ❌ BLOCKED: Multiple statements
validate_sql_query_safety(
    "SELECT * FROM users; DROP TABLE users"
)  # Raises: ValueError("Multiple statements detected")
```

---

## 4. Implementation Guide

### 4.1 Search & Filtering Capabilities

```mermaid
graph LR
    A[Search Query] --> B{Search Type}
    B -->|Similarity| C[Cosine Distance]
    B -->|Similarity| D[Euclidean Distance]
    B -->|Similarity| E[Dot Product]
    B -->|MMR| F[Diversity + Relevance]

    C --> G[Top K Results]
    D --> G
    E --> G
    F --> G

    G --> H{Apply Filters?}
    H -->|Yes| I[Metadata Filtering]
    H -->|No| J[Return Results]
    I --> J

    style A fill:#e1f5ff
    style G fill:#fff4e1
    style J fill:#e1ffe1
```

#### Distance Metrics Comparison

| Metric | Formula | Best For | Range |
|--------|---------|----------|-------|
| **Cosine** | `1 - (A·B)/(‖A‖‖B‖)` | Normalized vectors, text embeddings | [0, 2] |
| **Euclidean** | `√Σ(Ai-Bi)²` | Spatial data, image embeddings | [0, ∞) |
| **Dot Product** | `A·B` | Pre-normalized vectors | (-∞, ∞) |

#### Metadata Filtering Examples

```python
# Single condition
filter = {"category": "electronics"}

# Multiple conditions (AND)
filter = {
    "category": "electronics",
    "price": {"$lt": 1000}
}

# Range query
filter = {
    "price": {"$gte": 100, "$lte": 500},
    "tenant_id": "customer_123"
}
```

### 4.2 Search Types

```mermaid
graph TB
    subgraph "Similarity Search"
        A1[Query Vector] --> A2[Calculate Distance]
        A2 --> A3[Sort by Distance]
        A3 --> A4[Return Top K]
    end

    subgraph "MMR Search"
        B1[Query Vector] --> B2[Fetch K Candidates]
        B2 --> B3[Calculate Relevance]
        B3 --> B4[Calculate Diversity]
        B4 --> B5[Balance λ Parameter]
        B5 --> B6[Select Diverse K]
    end

    style A4 fill:#e1ffe1
    style B6 fill:#e1ffe1
```

**MMR Formula:**
```
MMR = λ × Similarity(query, doc) - (1-λ) × max(Similarity(doc, selected))
```

- `λ = 1.0`: Pure relevance (same as similarity search)
- `λ = 0.5`: Balanced relevance and diversity
- `λ = 0.0`: Maximum diversity

---

## 5. Testing & Quality Assurance

### 5.1 Test Coverage Strategy

```mermaid
graph TD
    A[Test Suite] --> B[Unit Tests 90%+]
    A --> C[Integration Tests]
    A --> D[Security Tests]
    A --> E[Performance Tests]

    B --> B1[Security Module]
    B --> B2[Helper Functions]
    B --> B3[Distance Calculations]

    C --> C1[DB2 Connection]
    C --> C2[Vector Operations]
    C --> C3[Search Operations]

    D --> D1[SQL Injection Prevention]
    D --> D2[Input Validation]
    D --> D3[Error Sanitization]

    E --> E1[Batch Operations]
    E --> E2[Query Latency]
    E --> E3[Concurrent Access]

    style B fill:#e1f5ff
    style C fill:#fff4e1
    style D fill:#ffe1e1
    style E fill:#e1ffe1
```

### 5.2 Security Test Coverage

| Test Category | Test Cases | Coverage |
|---------------|------------|----------|
| **Identifier Validation** | Valid identifiers, SQL injection attempts, reserved keywords | 15 tests |
| **String Sanitization** | Quote escaping, special characters, null handling | 8 tests |
| **Query Safety** | Operation whitelisting, multi-statements, comments | 12 tests |
| **Port Validation** | Valid ranges, type checking, boundary conditions | 6 tests |
| **Hostname Validation** | Valid formats, SQL metacharacters, injection patterns | 10 tests |

### 5.3 Test Execution

```bash
# Run all unit tests
make unit_tests

# Run security tests only
uv run pytest -k "security" src/backend/tests/unit/components/ibm/

# Run with coverage report
uv run pytest --cov=src/lfx/src/lfx/components/ibm --cov-report=html

# Run specific test file
uv run pytest src/backend/tests/unit/components/ibm/test_db2_security.py
```

---

## 6. Platform Guidelines & Best Practices

### 6.1 Langflow Component Standards

```mermaid
graph LR
    A[Component Definition] --> B[Input Definitions]
    A --> C[Output Definitions]
    A --> D[Build Method]

    B --> B1[Required Inputs]
    B --> B2[Advanced Inputs]
    B --> B3[Handle Inputs]

    C --> C1[Output Methods]
    C --> C2[Return Types]

    D --> D1[Validation]
    D --> D2[Processing]
    D --> D3[Error Handling]

    style A fill:#e1f5ff
    style D fill:#e1ffe1
```

### 6.2 Global Variable Usage

```mermaid
graph TB
    A[Global Variables] --> B[Generic Type]
    A --> C[Credential Type]

    B --> B1[Database Name]
    B --> B2[Hostname]
    B --> B3[Username]
    B --> B4[Port]

    C --> C1[Password ONLY]

    B1 --> D[Plain Text Storage]
    B2 --> D
    B3 --> D
    B4 --> D

    C1 --> E[Encrypted Storage]

    style B fill:#e1ffe1
    style C fill:#ffe1e1
    style D fill:#fff4e1
    style E fill:#ffe1e1
```

**Security Rule:** Only passwords use Credential-typed variables. All other connection parameters use Generic-typed variables.

### 6.3 Error Handling Pattern

```python
try:
    # Database operation
    connection = ibm_db_dbi.connect(conn_str, "", "")

except ibm_db_dbi.DatabaseError as e:
    # Database-specific errors
    safe_msg = create_safe_error_message(e, "while connecting")
    self.log(f"Connection failed: {safe_msg}")
    raise ConnectionError(safe_msg) from e

except Exception as e:
    # Generic errors
    safe_msg = create_safe_error_message(e, "during operation")
    self.log(f"Error: {safe_msg}")
    raise RuntimeError(safe_msg) from e

finally:
    # Always cleanup resources
    if cursor:
        cursor.close()
    if connection:
        connection.close()
```

### 6.4 Performance Best Practices

| Practice | Implementation | Benefit |
|----------|----------------|---------|
| **Batch Operations** | Insert 100-1000 docs at once | 10x faster than individual inserts |
| **Duplicate Detection** | Hash-based comparison (MD5) | Efficient memory usage |
| **Connection Pooling** | Reuse connections | Reduced connection overhead |
| **Query Timeout** | 30s default, configurable | Prevents resource exhaustion |
| **Pagination** | Fetch results in batches | Memory efficient for large datasets |

---

## 7. Deployment & Configuration

### 7.1 Setup Workflow

```mermaid
graph TD
    A[Start] --> B[Install Dependencies]
    B --> C[Configure DB2 Database]
    C --> D[Create Global Variables]
    D --> E[Add Components to Flow]
    E --> F[Configure Inputs]
    F --> G[Test Connection]
    G --> H{Success?}
    H -->|Yes| I[Deploy to Production]
    H -->|No| J[Troubleshoot]
    J --> G

    style A fill:#e1f5ff
    style I fill:#e1ffe1
    style J fill:#ffe1e1
```

### 7.2 Configuration Checklist

#### Prerequisites
```bash
# Install Python packages
uv add ibm_db ibm_db_dbi

# System dependencies (Linux)
sudo apt-get install gcc python3-dev

# System dependencies (macOS)
brew install gcc
```

#### Database Setup
```sql
-- Create database
CREATE DATABASE MYDB;

-- Grant permissions
GRANT CONNECT ON DATABASE TO USER db2user;
GRANT CREATETAB ON DATABASE TO USER db2user;
```

#### Langflow Configuration
1. **Create Generic Variables:**
   - `db2_database` = `MYDB`
   - `db2_hostname` = `db2.example.com`
   - `db2_username` = `db2user`

2. **Create Credential Variable:**
   - `db2_password` = `your_secure_password`

3. **Component Settings:**
   - Collection Name: `LANGFLOW_VECTORS`
   - Distance Strategy: `COSINE`
   - Search Type: `Similarity`
   - Number of Results: `4`

### 7.3 Monitoring & Health Checks

```python
# Connection health check
try:
    conn = ibm_db_dbi.connect(conn_str, "", "")
    conn.close()
    print("✓ DB2 connection successful")
except Exception as e:
    print(f"✗ DB2 connection failed: {e}")

# Performance metrics
self.log(f"Ingested {count} documents in {elapsed:.2f}s")
self.log(f"Search returned {len(results)} results in {latency:.0f}ms")
```

---

## 8. Troubleshooting Guide

### 8.1 Common Issues

```mermaid
graph TD
    A[Issue Detected] --> B{Error Type?}

    B -->|Connection| C[SQL30081N]
    B -->|Authentication| D[SQL30082N]
    B -->|Dimension| E[Embedding Mismatch]
    B -->|Security| F[Query Blocked]
    B -->|Variable| G[Type Error]

    C --> C1[Check hostname/port]
    C --> C2[Verify firewall rules]

    D --> D1[Verify credentials]
    D --> D2[Check user permissions]

    E --> E1[Use consistent model]
    E --> E2[Drop/recreate table]

    F --> F1[Remove SQL comments]
    F --> F2[Avoid multiple statements]

    G --> G1[Change to Generic type]
    G --> G2[Use Credential for password only]

    style A fill:#ffe1e1
    style C1 fill:#e1ffe1
    style C2 fill:#e1ffe1
    style D1 fill:#e1ffe1
    style D2 fill:#e1ffe1
    style E1 fill:#e1ffe1
    style E2 fill:#e1ffe1
    style F1 fill:#e1ffe1
    style F2 fill:#e1ffe1
    style G1 fill:#e1ffe1
    style G2 fill:#e1ffe1
```

### 8.2 Quick Solutions

| Error | Solution |
|-------|----------|
| **SQL30081N: Unable to connect** | Verify hostname, port, and firewall rules |
| **SQL30082N: Authentication failed** | Check username/password, ensure Credential variable for password |
| **Embedding dimension mismatch** | Use consistent embedding model or different table name |
| **Potentially unsafe SQL query** | Remove comments (`--`, `/**/`), avoid semicolons |
| **Credential-typed variable error** | Change to Generic type for non-password fields |

### 8.3 Debug Mode

```python
# Enable detailed logging
import logging
logging.getLogger('lfx.components.ibm').setLevel(logging.DEBUG)

# Test security functions
from lfx.components.ibm.db2_security import (
    validate_hostname,
    validate_port,
    validate_identifier
)

validate_hostname("db2.example.com")  # Should pass
validate_port(50000)  # Should pass
validate_identifier("my_table")  # Should pass
```

---

## 9. Performance Benchmarks

### 9.1 Operation Performance

| Operation | Documents | Time | Throughput |
|-----------|-----------|------|------------|
| **Insertion** | 1,000 | ~5s | 200 docs/s |
| **Insertion** | 10,000 | ~45s | 222 docs/s |
| **Search (k=10)** | 10,000 | ~50ms | 20 queries/s |
| **MMR (k=10)** | 10,000 | ~100ms | 10 queries/s |

*Benchmarks: DB2 11.5, 4 CPU, 16GB RAM*

### 9.2 Optimization Tips

```mermaid
graph LR
    A[Optimization] --> B[Batch Size]
    A --> C[Connection Pooling]
    A --> D[Indexing]
    A --> E[Caching]

    B --> B1[500-1000 docs/batch]
    C --> C1[Reuse connections]
    D --> D1[Index metadata fields]
    E --> E1[Cache vector store]

    style A fill:#e1f5ff
    style B1 fill:#e1ffe1
    style C1 fill:#e1ffe1
    style D1 fill:#e1ffe1
    style E1 fill:#e1ffe1
```

---

## 10. Summary & Resources

### 10.1 Key Takeaways

✅ **Security-First Design**: Multi-layer defense against SQL injection and data breaches
✅ **Production-Ready**: Comprehensive error handling, monitoring, and performance optimization
✅ **Developer-Friendly**: Clear APIs, extensive documentation, and intuitive components
✅ **Enterprise-Grade**: Leverages IBM DB2's robust infrastructure for scalable AI applications

### 10.2 Resources

- **IBM DB2 Documentation**: [ibm.com/docs/en/db2/11.5](https://www.ibm.com/docs/en/db2/11.5)
- **Langflow Documentation**: [docs.langflow.org](https://docs.langflow.org/)
- **Component Guide**: `src/lfx/src/lfx/components/ibm/DB2_VARIABLE_USAGE.md`
- **Security Module**: `src/lfx/src/lfx/components/ibm/db2_security.py`

### 10.3 Support

For issues or questions:
1. Review this documentation
2. Check component info text (hover ℹ️ icon)
3. Consult Langflow documentation
4. Contact system administrator

---

**Document Version**: 1.0
**Last Updated**: May 2026
**Maintained By**: Langflow IBM Integration Team
**License**: MIT
