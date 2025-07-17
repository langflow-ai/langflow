import math
from collections import Counter


def compute_tfidf(documents: list[str], query_terms: list[str]) -> list[float]:
    """Compute TF-IDF scores for query terms across a collection of documents.

    Args:
        documents: List of document strings
        query_terms: List of query terms to score

    Returns:
        List of TF-IDF scores for each document
    """
    # Lowercase query terms once
    query_terms_lc = [term.lower() for term in query_terms]
    query_terms_set = set(query_terms_lc)

    # Tokenize documents (simple whitespace splitting) and lowercase all at once
    tokenized_docs = []
    token_sets = []
    for doc in documents:
        tokens = doc.lower().split()
        tokenized_docs.append(tokens)
        token_sets.append(set(tokens))

    n_docs = len(tokenized_docs)

    # Calculate document frequency for each query term (single pass over docs)
    document_frequencies = dict.fromkeys(query_terms_lc, 0)
    for token_set in token_sets:
        for term in query_terms_set:
            if term in token_set:
                document_frequencies[term] += 1

    # Precompute IDF values for all query terms
    idf_values = {}
    for term in query_terms_lc:
        df = document_frequencies[term]
        idf = math.log(n_docs / df) if df > 0 else 0
        idf_values[term] = idf

    scores = []
    for tokens in tokenized_docs:
        doc_len = len(tokens)
        if doc_len == 0:
            scores.append(0.0)
            continue
        # Build freq dict quickly for doc
        term_counts = {}
        for token in tokens:
            if token in query_terms_set:
                term_counts[token] = term_counts.get(token, 0) + 1

        doc_score = 0.0
        for term in query_terms_lc:
            tf = term_counts.get(term, 0) / doc_len
            doc_score += tf * idf_values[term]
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
            idf = (
                math.log((n_docs - document_frequencies[term] + 0.5) / (document_frequencies[term] + 0.5))
                if document_frequencies[term] > 0
                else 0
            )

            # BM25 score calculation
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))

            doc_score += idf * (numerator / denominator)

        scores.append(doc_score)

    return scores
