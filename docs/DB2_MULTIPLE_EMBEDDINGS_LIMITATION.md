# DB2 Vector Store - Multiple Embedding Columns Limitation

## Issue Description

**Reported By:** User
**Date:** 2026-05-18
**Status:** Known Limitation - Enhancement Needed

## Problem

The current implementation of `DB2VS` assumes **one embedding column per table**. If a user has multiple embedding columns (e.g., from different embedding models), the system cannot specify which column to use for retrieval.

### Example Scenario

```sql
CREATE TABLE PRODUCTS (
    ID VARCHAR(255) PRIMARY KEY,
    TEXT CLOB,
    METADATA CLOB,
    EMBEDDING_OPENAI VECTOR(1536),   -- OpenAI ada-002
    EMBEDDING_COHERE VECTOR(1024),   -- Cohere embed-v3
    EMBEDDING_MISTRAL VECTOR(1024)   -- Mistral embed
);
```

**Current Behavior:**
- The `_get_column_names()` function looks for columns named: `embedding`, `vector`, or `embeddings`
- It returns the FIRST match found
- User cannot specify which embedding column to use
- If dimensions don't match, retrieval fails

**Expected Behavior:**
- User should be able to specify: `embedding_column="EMBEDDING_OPENAI"`
- System should use that specific column for all operations
- Multiple `DB2VS` instances should be able to work with different embedding columns in the same table

## Current Code (Lines 151-154)

```python
# EMBEDDING column
column_map["embedding"] = actual_columns.get(
    "embedding", actual_columns.get("vector", actual_columns.get("embeddings", '"embedding"'))
)
```

This hardcoded logic cannot handle custom column names.

## Proposed Solution

### 1. Add `embedding_column` Parameter

**File:** `src/lfx/src/lfx/components/ibm/db2vs.py`

```python
def __init__(
    self,
    client: Connection,
    embedding_function: Callable[[str], list[float]] | Embeddings,
    table_name: str,
    embedding_column: str = "embedding",  # NEW PARAMETER
    distance_strategy: DistanceStrategy = DistanceStrategy.EUCLIDEAN_DISTANCE,
    query: str | None = "What is a Db2 database",
    params: dict[str, Any] | None = None,
):
    """Initialize DB2 vector store with security validations.

    Args:
        client: IBM DB2 database connection
        embedding_function: Function or Embeddings object to generate embeddings
        table_name: Name of the table to store vectors (will be validated)
        embedding_column: Name of the embedding column to use (default: "embedding")
        distance_strategy: Strategy for distance calculation
        query: Optional default query
        params: Optional additional parameters
    """
    # Validate embedding column name
    validated_embedding_column = validate_identifier(embedding_column, "embedding column")
    self.embedding_column = validated_embedding_column

    # Pass to column detection
    self.column_names = _get_column_names(
        client,
        validated_table_name,
        embedding_column=validated_embedding_column  # NEW
    )
```

### 2. Update `_get_column_names()` Function

```python
def _get_column_names(
    client: Connection,
    table_name: str,
    embedding_column: str = "embedding"  # NEW PARAMETER
) -> dict[str, str]:
    """Detect actual column names in the table.

    Args:
        client: Database connection
        table_name: Table name
        embedding_column: Specific embedding column to use (default: "embedding")
    """
    # ... existing code ...

    # EMBEDDING column - use specified column or fall back to aliases
    if embedding_column.lower() in actual_columns:
        column_map["embedding"] = actual_columns[embedding_column.lower()]
    else:
        # Fall back to aliases if specified column not found
        column_map["embedding"] = actual_columns.get(
            "embedding",
            actual_columns.get("vector",
                actual_columns.get("embeddings", f'"{embedding_column}"')
            )
        )

    return column_map
```

### 3. Update Component Interface

**File:** `src/lfx/src/lfx/components/ibm/db2_vector.py`

```python
inputs = [
    StrInput(
        name="collection_name",
        display_name="Table Name",
        value="LANGFLOW_VECTORS",
        required=True,
    ),
    StrInput(
        name="embedding_column",  # NEW INPUT
        display_name="Embedding Column Name",
        value="embedding",
        advanced=True,
        info="Name of the column storing embeddings (default: 'embedding'). "
             "Use this if your table has multiple embedding columns.",
    ),
    # ... rest of inputs ...
]

def build_vector_store(self):
    # ... existing code ...

    vector_store = DB2VS(
        client=connection,
        embedding_function=self.embedding,
        table_name=validated_table_name,
        embedding_column=self.embedding_column,  # NEW
        distance_strategy=distance_strategy_map.get(
            self.distance_strategy,
            DistanceStrategy.COSINE
        ),
    )
```

## Use Case Example

After implementation, users could do:

```python
# Instance 1: Use OpenAI embeddings
vector_store_openai = DB2VS(
    client=connection,
    embedding_function=openai_embeddings,
    table_name="PRODUCTS",
    embedding_column="EMBEDDING_OPENAI"  # Specify column
)

# Instance 2: Use Cohere embeddings on SAME table
vector_store_cohere = DB2VS(
    client=connection,
    embedding_function=cohere_embeddings,
    table_name="PRODUCTS",
    embedding_column="EMBEDDING_COHERE"  # Different column
)

# Both work on the same table with different embedding columns!
results_openai = vector_store_openai.similarity_search("laptop", k=5)
results_cohere = vector_store_cohere.similarity_search("laptop", k=5)
```

## Benefits

1. **Multi-Model Support**: Use different embedding models on the same data
2. **A/B Testing**: Compare embedding model performance
3. **Migration**: Gradually migrate from one embedding model to another
4. **Flexibility**: Support custom column naming conventions

## Workaround (Current)

Until this is implemented, users must:
1. Use separate tables for each embedding model
2. Ensure their embedding column is named exactly `embedding`, `vector`, or `embeddings`
3. Cannot have multiple embedding columns in the same table

## Priority

**Medium-High** - This is a common use case in production environments where:
- Teams want to compare embedding models
- Organizations migrate between embedding providers
- Different use cases require different embedding dimensions

## Implementation Effort

**Estimated:** 2-3 hours
- Modify `__init__` signature (15 min)
- Update `_get_column_names()` logic (30 min)
- Update component inputs (15 min)
- Add validation (30 min)
- Write tests (1 hour)
- Update documentation (30 min)

## Related Files

- `src/lfx/src/lfx/components/ibm/db2vs.py` (lines 342-421, 95-159)
- `src/lfx/src/lfx/components/ibm/db2_vector.py` (lines 31-136)
- `src/backend/tests/unit/components/ibm/test_db2vs.py`

---

**Status:** Documented as known limitation
**Next Steps:** Prioritize for next sprint based on user demand