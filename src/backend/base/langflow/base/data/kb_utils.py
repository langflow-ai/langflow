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
    # Preprocess: lowercased documents and terms
    lc_documents = [doc.lower().split() for doc in documents]
    n_docs = len(lc_documents)
    if n_docs == 0:
        return []

    avg_doc_length = sum(len(doc) for doc in lc_documents) / n_docs if n_docs > 0 else 0
    if avg_doc_length == 0:
        return [0.0] * n_docs

    # Only use lowercased query terms, and unique set for lookup
    lc_query_terms = [q.lower() for q in query_terms]
    query_term_set = set(lc_query_terms)

    # Compute document frequencies for all query terms
    doc_freqs = {term: 0 for term in query_term_set}
    for doc in lc_documents:
        present_terms = set(doc) & query_term_set
        for term in present_terms:
            doc_freqs[term] += 1

    # Precompute idf for all terms
    idf = {}
    for term in lc_query_terms:
        freq = doc_freqs[term]
        if freq > 0:
            idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5))
        else:
            idf[term] = 0.0

    scores = []
    for doc in lc_documents:
        doc_len = len(doc)
        if doc_len == 0:
            scores.append(0.0)
            continue

        # Fast term counting for relevant terms
        tf = {}
        for term in doc:
            if term in query_term_set:
                tf[term] = tf.get(term, 0) + 1

        norm = k1 * (1 - b + b * (doc_len / avg_doc_length))

        doc_score = 0.0
        for term in lc_query_terms:
            freq = tf.get(term, 0)
            if freq == 0 or idf[term] == 0.0:
                continue
            numer = freq * (k1 + 1)
            denom = freq + norm
            doc_score += idf[term] * (numer / denom)

        scores.append(doc_score)

    return scores
