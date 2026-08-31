import math
from collections import Counter
from uuid import UUID


def compute_tfidf(documents: list[str], query_terms: list[str]) -> list[float]:
    """Compute TF-IDF scores for query terms across a collection of documents.

    Args:
        documents: List of document strings
        query_terms: List of query terms to score

    Returns:
        List of TF-IDF scores for each document
    """
    # Tokenize documents (simple whitespace splitting)
    tokenized_docs = [doc.lower().split() for doc in documents]
    n_docs = len(documents)

    # Calculate document frequency for each term
    document_frequencies = {}
    for term in query_terms:
        document_frequencies[term] = sum(1 for doc in tokenized_docs if term.lower() in doc)

    scores = []

    for doc_tokens in tokenized_docs:
        doc_score = 0.0
        doc_length = len(doc_tokens)
        term_counts = Counter(doc_tokens)

        for term in query_terms:
            term_lower = term.lower()

            # Term frequency (TF)
            tf = term_counts[term_lower] / doc_length if doc_length > 0 else 0

            # Inverse document frequency (IDF)
            idf = math.log(n_docs / document_frequencies[term]) if document_frequencies[term] > 0 else 0

            # TF-IDF score
            doc_score += tf * idf

        scores.append(doc_score)

    return scores


def compute_bm25(documents: list[str], query_terms: list[str], k1: float = 1.2, b: float = 0.75) -> list[float]:
    """Compute BM25 scores for query terms across a collection of documents.

    Args:
        documents: List of document strings
        query_terms: List of query terms to score
        k1: Controls term frequency scaling (default: 1.2)
        b: Controls document length normalization (default: 0.75)

    Returns:
        List of BM25 scores for each document
    """
    # Tokenize documents
    tokenized_docs = [doc.lower().split() for doc in documents]
    n_docs = len(documents)

    # Calculate average document length
    avg_doc_length = sum(len(doc) for doc in tokenized_docs) / n_docs if n_docs > 0 else 0

    # Handle edge case where all documents are empty
    if avg_doc_length == 0:
        return [0.0] * n_docs

    # Calculate document frequency for each term
    document_frequencies = {}
    for term in query_terms:
        document_frequencies[term] = sum(1 for doc in tokenized_docs if term.lower() in doc)

    scores = []

    for doc_tokens in tokenized_docs:
        doc_score = 0.0
        doc_length = len(doc_tokens)
        term_counts = Counter(doc_tokens)

        for term in query_terms:
            term_lower = term.lower()

            # Term frequency in document
            tf = term_counts[term_lower]

            # Inverse document frequency (IDF)
            # Use standard BM25 IDF formula that ensures non-negative values
            idf = math.log(n_docs / document_frequencies[term]) if document_frequencies[term] > 0 else 0

            # BM25 score calculation
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))

            # Handle division by zero when tf=0 and k1=0
            term_score = 0 if denominator == 0 else idf * (numerator / denominator)

            doc_score += term_score

        scores.append(doc_score)

    return scores


async def get_knowledge_bases(user_id: UUID | str) -> list[str]:
    """Retrieve a list of available knowledge bases for ``user_id``.

    Reads ``knowledge_base`` rows only, matching the ``GET /knowledge_bases/``
    endpoint that backs the Knowledge management page, so the canvas component
    dropdown stays in sync with that page.

    No disk scan: a remote-backed KB has no local directory to find, and scanning
    would surface any directory left behind by a delete that could not remove its
    bytes — entries that no longer exist as far as the management page is
    concerned. Directories written by a version that predates the row are adopted
    via ``langflow reconcile-kb-from-disk``.

    Memory-Base-associated KBs are skipped; those are surfaced through the
    dedicated Memory Base APIs.

    Returns:
        A list of knowledge base names.
    """
    # Lazy imports: langflow's DB models aren't part of the lfx
    # standalone install, and lfx's validate-rewrite layer can't
    # substitute ``lfx.services.database.models.user.crud`` (no such
    # module). Deferring the imports to call time keeps this module
    # importable under ``lfx run <starter>.json``, which is exercised
    # by the starter-projects smoke test.
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.deps import session_scope
    from sqlmodel import select

    if not user_id:
        msg = "User ID is required for fetching knowledge bases."
        raise ValueError(msg)
    user_id = UUID(user_id) if isinstance(user_id, str) else user_id

    async with session_scope() as db:
        stmt = select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.user_id == user_id)
        rows = list((await db.exec(stmt)).all())

    return [row.name for row in rows if not (isinstance(row.source_types, list) and "memory" in row.source_types)]
