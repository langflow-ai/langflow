import math
from collections import Counter
from pathlib import Path
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


async def get_knowledge_bases(kb_root: Path, user_id: UUID | str) -> list[str]:
    """Retrieve a list of available knowledge bases for ``user_id``.

    DB-first, with a disk-scan fallback. This mirrors the semantics of
    the ``GET /knowledge_bases/`` API endpoint that backs the Knowledge
    management page, so the canvas component dropdown stays in sync with
    that page. The disk scan is only used when the user has zero
    ``knowledge_base`` rows -- the same recovery path the API endpoint
    uses for legacy/exported KB directories that have not yet been
    reconciled into the DB.

    Without the DB-first behavior, the dropdown would surface any KB
    directory left on disk after a deletion that did not write the
    ``.kb_deleted`` sentinel (e.g. legacy deletes from before the
    sentinel system, direct ``DELETE FROM knowledge_base`` cleanups, or
    DB resets that left the filesystem intact). Those entries no longer
    exist as far as the management page is concerned, but the prior
    disk-only listing would still show them.

    The disk fallback continues to skip dot-prefixed entries (legacy
    hidden bundles) and any directory carrying the ``.kb_deleted``
    sentinel.

    Returns:
        A list of knowledge base names.
    """
    if not kb_root.exists():
        return []

    # Lazy imports: langflow's DB models aren't part of the lfx
    # standalone install, and lfx's validate-rewrite layer can't
    # substitute ``lfx.services.database.models.user.crud`` (no such
    # module). Deferring the imports to call time keeps this module
    # importable under ``lfx run <starter>.json``, which is exercised
    # by the starter-projects smoke test.
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.database.models.user.crud import get_user_by_id
    from langflow.services.deps import session_scope
    from sqlmodel import select

    # Get the current user
    async with session_scope() as db:
        if not user_id:
            msg = "User ID is required for fetching knowledge bases."
            raise ValueError(msg)
        user_id = UUID(user_id) if isinstance(user_id, str) else user_id
        current_user = await get_user_by_id(db, user_id)
        if not current_user:
            msg = f"User with ID {user_id} not found."
            raise ValueError(msg)
        kb_user = current_user.username

        # DB-first: when the user has KB rows, those are authoritative.
        # Skip memory-base-associated KBs to match the listing endpoint
        # (those are surfaced through dedicated Memory Base APIs).
        stmt = select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.user_id == user_id)
        rows = list((await db.exec(stmt)).all())

    if rows:
        return [row.name for row in rows if not (isinstance(row.source_types, list) and "memory" in row.source_types)]

    kb_path = kb_root / kb_user

    if not kb_path.exists():
        return []

    # Recovery-only disk fallback for users with zero DB rows. Inlined
    # sentinel check: lfx must stay importable without the langflow API
    # package, so we cannot reach for KBStorageHelper. The string literal
    # is kept in lockstep with KB_DELETED_SENTINEL in
    # src/backend/base/langflow/api/utils/kb_helpers.py via a unit test
    # that asserts the two values are equal.
    deleted_marker = ".kb_deleted"
    return [
        str(d.name)
        for d in kb_path.iterdir()
        if not d.name.startswith(".") and d.is_dir() and not (d / deleted_marker).is_file()
    ]
