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
    # Tokenize documents (simple whitespace splitting) and lower once
    tokenized_docs = [doc.lower().split() for doc in documents]
    n_docs = len(documents)

    # Cache lowercased query_terms for speed
    query_terms_lower = [term.lower() for term in query_terms]
    query_term_set = set(query_terms_lower)

    # Calculate document frequency for each query term in one pass
    df = dict.fromkeys(query_terms_lower, 0)
    for doc_tokens in tokenized_docs:
        seen = set()
        for token in doc_tokens:
            if token in query_term_set:
                seen.add(token)
        for token in seen:
            df[token] += 1

    # Precompute idf for each term once
    idf = {}
    for term in query_terms_lower:
        doc_freq = df[term]
        idf[term] = math.log(n_docs / doc_freq) if doc_freq > 0 else 0

    # Compute scores efficiently
    scores = []
    for doc_tokens in tokenized_docs:
        doc_score = 0.0
        doc_length = len(doc_tokens)
        if doc_length == 0:
            scores.append(0.0)
            continue
        term_counts = Counter(doc_tokens)
        # Only iterate relevant query terms
        for term in query_terms_lower:
            tf = term_counts[term] / doc_length if term in term_counts else 0.0
            doc_score += tf * idf[term]
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

    # Calculate document frequency for each term
    df = {}
    for term in query_terms:
        df[term] = sum(1 for doc in tokenized_docs if term.lower() in doc)

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
            idf = math.log((n_docs - df[term] + 0.5) / (df[term] + 0.5)) if df[term] > 0 else 0

            # BM25 score calculation
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))

            doc_score += idf * (numerator / denominator)

        scores.append(doc_score)

    return scores


# Example usage
if __name__ == "__main__":
    # Sample documents
    docs = [
        "The quick brown fox jumps over the lazy dog",
        "A quick brown dog runs fast",
        "The lazy cat sleeps all day",
        "Brown animals are quick and fast",
    ]

    # Query terms
    query = ["quick", "brown"]

    # Compute TF-IDF scores
    tfidf_scores = compute_tfidf(docs, query)
    print("TF-IDF Scores:")
    for i, score in enumerate(tfidf_scores):
        print(f"Document {i + 1}: {score:.4f}")

    print("\n" + "=" * 40 + "\n")

    # Compute BM25 scores
    bm25_scores = compute_bm25(docs, query)
    print("BM25 Scores:")
    for i, score in enumerate(bm25_scores):
        print(f"Document {i + 1}: {score:.4f}")
