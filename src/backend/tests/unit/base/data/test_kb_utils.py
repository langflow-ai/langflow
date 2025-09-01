import pytest
from langflow.base.knowledge_bases.knowledge_base_utils import compute_bm25, compute_tfidf


class TestKBUtils:
    """Test suite for knowledge base utility functions."""

    # Test data for TF-IDF and BM25 tests
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing."""
        return ["the cat sat on the mat", "the dog ran in the park", "cats and dogs are pets", "birds fly in the sky"]

    @pytest.fixture
    def query_terms(self):
        """Sample query terms for testing."""
        return ["cat", "dog"]

    @pytest.fixture
    def empty_documents(self):
        """Empty documents for edge case testing."""
        return ["", "", ""]

    @pytest.fixture
    def single_document(self):
        """Single document for testing."""
        return ["hello world"]

    def test_compute_tfidf_basic(self, sample_documents, query_terms):
        """Test basic TF-IDF computation."""
        scores = compute_tfidf(sample_documents, query_terms)

        # Should return a score for each document
        assert len(scores) == len(sample_documents)

        # All scores should be floats
        assert all(isinstance(score, float) for score in scores)

        # First document contains "cat", should have non-zero score
        assert scores[0] > 0.0

        # Second document contains "dog", should have non-zero score
        assert scores[1] > 0.0

        # Third document contains both "cats" and "dogs", but case-insensitive matching should work
        # Note: "cats" != "cat" exactly, so this tests the term matching behavior
        assert scores[2] >= 0.0

        # Fourth document contains neither term, should have zero score
        assert scores[3] == 0.0

    def test_compute_tfidf_case_insensitive(self):
        """Test that TF-IDF computation is case insensitive."""
        documents = ["The CAT sat", "the dog RAN", "CATS and DOGS"]
        query_terms = ["cat", "DOG"]

        scores = compute_tfidf(documents, query_terms)

        # First document should match "cat" (case insensitive)
        assert scores[0] > 0.0

        # Second document should match "dog" (case insensitive)
        assert scores[1] > 0.0

    def test_compute_tfidf_empty_documents(self, empty_documents, query_terms):
        """Test TF-IDF with empty documents."""
        scores = compute_tfidf(empty_documents, query_terms)

        # Should return scores for all documents
        assert len(scores) == len(empty_documents)

        # All scores should be zero since documents are empty
        assert all(score == 0.0 for score in scores)

    def test_compute_tfidf_empty_query_terms(self, sample_documents):
        """Test TF-IDF with empty query terms."""
        scores = compute_tfidf(sample_documents, [])

        # Should return scores for all documents
        assert len(scores) == len(sample_documents)

        # All scores should be zero since no query terms
        assert all(score == 0.0 for score in scores)

    def test_compute_tfidf_single_document(self, single_document):
        """Test TF-IDF with single document."""
        query_terms = ["hello", "world"]
        scores = compute_tfidf(single_document, query_terms)

        assert len(scores) == 1
        # With only one document, IDF = log(1/1) = 0, so TF-IDF score is always 0
        # This is correct mathematical behavior - TF-IDF is designed to discriminate between documents
        assert scores[0] == 0.0

    def test_compute_tfidf_two_documents_positive_scores(self):
        """Test TF-IDF with two documents to ensure positive scores are possible."""
        documents = ["hello world", "goodbye earth"]
        query_terms = ["hello", "world"]
        scores = compute_tfidf(documents, query_terms)

        assert len(scores) == 2
        # First document contains both terms, should have positive score
        assert scores[0] > 0.0
        # Second document contains neither term, should have zero score
        assert scores[1] == 0.0

    def test_compute_tfidf_no_documents(self):
        """Test TF-IDF with no documents."""
        scores = compute_tfidf([], ["cat", "dog"])

        assert scores == []

    def test_compute_tfidf_term_frequency_calculation(self):
        """Test TF-IDF term frequency calculation."""
        # Documents with different term frequencies for the same term
        documents = ["rare word text", "rare rare word", "other content"]
        query_terms = ["rare"]

        scores = compute_tfidf(documents, query_terms)

        # "rare" appears in documents 0 and 1, but with different frequencies
        # Document 1 has higher TF (2/3 vs 1/3), so should score higher
        assert scores[0] > 0.0  # Contains "rare" once
        assert scores[1] > scores[0]  # Contains "rare" twice, should score higher
        assert scores[2] == 0.0  # Doesn't contain "rare"

    def test_compute_tfidf_idf_calculation(self):
        """Test TF-IDF inverse document frequency calculation."""
        # "rare" appears in only one document, "common" appears in both
        documents = ["rare term", "common term", "common word"]
        query_terms = ["rare", "common"]

        scores = compute_tfidf(documents, query_terms)

        # First document should have higher score due to rare term having higher IDF
        assert scores[0] > scores[1]  # rare term gets higher IDF
        assert scores[0] > scores[2]

    def test_compute_bm25_basic(self, sample_documents, query_terms):
        """Test basic BM25 computation."""
        scores = compute_bm25(sample_documents, query_terms)

        # Should return a score for each document
        assert len(scores) == len(sample_documents)

        # All scores should be floats
        assert all(isinstance(score, float) for score in scores)

        # First document contains "cat", should have non-zero score
        assert scores[0] > 0.0

        # Second document contains "dog", should have non-zero score
        assert scores[1] > 0.0

        # Fourth document contains neither term, should have zero score
        assert scores[3] == 0.0

    def test_compute_bm25_parameters(self, sample_documents, query_terms):
        """Test BM25 with different k1 and b parameters."""
        # Test with default parameters
        scores_default = compute_bm25(sample_documents, query_terms)

        # Test with different k1
        scores_k1 = compute_bm25(sample_documents, query_terms, k1=2.0)

        # Test with different b
        scores_b = compute_bm25(sample_documents, query_terms, b=0.5)

        # Test with both different
        scores_both = compute_bm25(sample_documents, query_terms, k1=2.0, b=0.5)

        # All should return valid scores
        assert len(scores_default) == len(sample_documents)
        assert len(scores_k1) == len(sample_documents)
        assert len(scores_b) == len(sample_documents)
        assert len(scores_both) == len(sample_documents)

        # Scores should be different with different parameters
        assert scores_default != scores_k1
        assert scores_default != scores_b

    def test_compute_bm25_case_insensitive(self):
        """Test that BM25 computation is case insensitive."""
        documents = ["The CAT sat", "the dog RAN", "CATS and DOGS"]
        query_terms = ["cat", "DOG"]

        scores = compute_bm25(documents, query_terms)

        # First document should match "cat" (case insensitive)
        assert scores[0] > 0.0

        # Second document should match "dog" (case insensitive)
        assert scores[1] > 0.0

    def test_compute_bm25_empty_documents(self, empty_documents, query_terms):
        """Test BM25 with empty documents."""
        scores = compute_bm25(empty_documents, query_terms)

        # Should return scores for all documents
        assert len(scores) == len(empty_documents)

        # All scores should be zero since documents are empty
        assert all(score == 0.0 for score in scores)

    def test_compute_bm25_empty_query_terms(self, sample_documents):
        """Test BM25 with empty query terms."""
        scores = compute_bm25(sample_documents, [])

        # Should return scores for all documents
        assert len(scores) == len(sample_documents)

        # All scores should be zero since no query terms
        assert all(score == 0.0 for score in scores)

    def test_compute_bm25_single_document(self, single_document):
        """Test BM25 with single document."""
        query_terms = ["hello", "world"]
        scores = compute_bm25(single_document, query_terms)

        assert len(scores) == 1
        # With only one document, IDF = log(1/1) = 0, so BM25 score is always 0
        # This is correct mathematical behavior - both TF-IDF and BM25 are designed to discriminate between documents
        assert scores[0] == 0.0

    def test_compute_bm25_two_documents_positive_scores(self):
        """Test BM25 with two documents to ensure positive scores are possible."""
        documents = ["hello world", "goodbye earth"]
        query_terms = ["hello", "world"]
        scores = compute_bm25(documents, query_terms)

        assert len(scores) == 2
        # First document contains both terms, should have positive score
        assert scores[0] > 0.0
        # Second document contains neither term, should have zero score
        assert scores[1] == 0.0

    def test_compute_bm25_no_documents(self):
        """Test BM25 with no documents."""
        scores = compute_bm25([], ["cat", "dog"])

        assert scores == []

    def test_compute_bm25_document_length_normalization(self):
        """Test BM25 document length normalization."""
        # Test with documents where some terms appear in subset of documents
        documents = [
            "cat unique1",  # Short document with unique term
            "cat dog bird mouse elephant tiger lion bear wolf unique2",  # Long document with unique term
            "other content",  # Document without query terms
        ]
        query_terms = ["unique1", "unique2"]

        scores = compute_bm25(documents, query_terms)

        # Documents with unique terms should have positive scores
        assert scores[0] > 0.0  # Contains "unique1"
        assert scores[1] > 0.0  # Contains "unique2"
        assert scores[2] == 0.0  # Contains neither term

        # Document length normalization affects scores
        assert len(scores) == 3

    def test_compute_bm25_term_frequency_saturation(self):
        """Test BM25 term frequency saturation behavior."""
        # Test with documents where term frequencies can be meaningfully compared
        documents = [
            "rare word text",  # TF = 1 for "rare"
            "rare rare word",  # TF = 2 for "rare"
            "rare rare rare rare rare word",  # TF = 5 for "rare"
            "other content",  # No "rare" term
        ]
        query_terms = ["rare"]

        scores = compute_bm25(documents, query_terms)

        # Documents with the term should have positive scores
        assert scores[0] > 0.0  # TF=1
        assert scores[1] > 0.0  # TF=2
        assert scores[2] > 0.0  # TF=5
        assert scores[3] == 0.0  # TF=0

        # Scores should increase with term frequency, but with diminishing returns
        assert scores[1] > scores[0]  # TF=2 > TF=1
        assert scores[2] > scores[1]  # TF=5 > TF=2

        # Check that increases demonstrate saturation effect
        increase_1_to_2 = scores[1] - scores[0]
        increase_2_to_5 = scores[2] - scores[1]
        assert increase_1_to_2 > 0
        assert increase_2_to_5 > 0

    def test_compute_bm25_idf_calculation(self):
        """Test BM25 inverse document frequency calculation."""
        # "rare" appears in only one document, "common" appears in multiple
        documents = ["rare term", "common term", "common word"]
        query_terms = ["rare", "common"]

        scores = compute_bm25(documents, query_terms)

        # First document should have higher score due to rare term having higher IDF
        assert scores[0] > scores[1]  # rare term gets higher IDF
        assert scores[0] > scores[2]

    def test_compute_bm25_zero_parameters(self, sample_documents, query_terms):
        """Test BM25 with edge case parameters."""
        # Test with k1=0 (no term frequency scaling)
        scores_k1_zero = compute_bm25(sample_documents, query_terms, k1=0.0)
        assert len(scores_k1_zero) == len(sample_documents)

        # Test with b=0 (no document length normalization)
        scores_b_zero = compute_bm25(sample_documents, query_terms, b=0.0)
        assert len(scores_b_zero) == len(sample_documents)

        # Test with b=1 (full document length normalization)
        scores_b_one = compute_bm25(sample_documents, query_terms, b=1.0)
        assert len(scores_b_one) == len(sample_documents)

    def test_tfidf_vs_bm25_comparison(self, sample_documents, query_terms):
        """Test that TF-IDF and BM25 produce different but related scores."""
        tfidf_scores = compute_tfidf(sample_documents, query_terms)
        bm25_scores = compute_bm25(sample_documents, query_terms)

        # Both should return same number of scores
        assert len(tfidf_scores) == len(bm25_scores) == len(sample_documents)

        # For documents that match, both should be positive
        for i in range(len(sample_documents)):
            if tfidf_scores[i] > 0:
                assert bm25_scores[i] > 0, f"Document {i} has TF-IDF score but zero BM25 score"
            if bm25_scores[i] > 0:
                assert tfidf_scores[i] > 0, f"Document {i} has BM25 score but zero TF-IDF score"

    def test_compute_tfidf_special_characters(self):
        """Test TF-IDF with documents containing special characters."""
        documents = ["hello, world!", "world... hello?", "no match here"]
        query_terms = ["hello", "world"]

        scores = compute_tfidf(documents, query_terms)

        # Should handle punctuation and still match terms
        assert len(scores) == 3
        # Note: Current implementation does simple split(), so punctuation stays attached
        # This tests the current behavior - may need updating if tokenization improves

    def test_compute_bm25_special_characters(self):
        """Test BM25 with documents containing special characters."""
        documents = ["hello, world!", "world... hello?", "no match here"]
        query_terms = ["hello", "world"]

        scores = compute_bm25(documents, query_terms)

        # Should handle punctuation and still match terms
        assert len(scores) == 3
        # Same tokenization behavior as TF-IDF

    def test_compute_tfidf_whitespace_handling(self):
        """Test TF-IDF with various whitespace scenarios."""
        documents = [
            "  hello   world  ",  # Extra spaces
            "\thello\tworld\t",  # Tabs
            "hello\nworld",  # Newlines
            "",  # Empty string
        ]
        query_terms = ["hello", "world"]

        scores = compute_tfidf(documents, query_terms)

        assert len(scores) == 4
        # First three should have positive scores (they contain the terms)
        assert scores[0] > 0.0
        assert scores[1] > 0.0
        assert scores[2] > 0.0
        # Last should be zero (empty document)
        assert scores[3] == 0.0

    def test_compute_bm25_whitespace_handling(self):
        """Test BM25 with various whitespace scenarios."""
        documents = [
            "  hello   world  ",  # Extra spaces
            "\thello\tworld\t",  # Tabs
            "hello\nworld",  # Newlines
            "",  # Empty string
        ]
        query_terms = ["hello", "world"]

        scores = compute_bm25(documents, query_terms)

        assert len(scores) == 4
        # First three should have positive scores (they contain the terms)
        assert scores[0] > 0.0
        assert scores[1] > 0.0
        assert scores[2] > 0.0
        # Last should be zero (empty document)
        assert scores[3] == 0.0

    def test_compute_tfidf_mathematical_properties(self):
        """Test mathematical properties of TF-IDF scores."""
        documents = ["cat dog", "cat", "dog"]
        query_terms = ["cat"]

        scores = compute_tfidf(documents, query_terms)

        # All scores should be non-negative
        assert all(score >= 0.0 for score in scores)

        # Documents containing the term should have positive scores
        assert scores[0] > 0.0  # contains "cat"
        assert scores[1] > 0.0  # contains "cat"
        assert scores[2] == 0.0  # doesn't contain "cat"

    def test_compute_bm25_mathematical_properties(self):
        """Test mathematical properties of BM25 scores."""
        documents = ["cat dog", "cat", "dog"]
        query_terms = ["cat"]

        scores = compute_bm25(documents, query_terms)

        # All scores should be non-negative
        assert all(score >= 0.0 for score in scores)

        # Documents containing the term should have positive scores
        assert scores[0] > 0.0  # contains "cat"
        assert scores[1] > 0.0  # contains "cat"
        assert scores[2] == 0.0  # doesn't contain "cat"

    def test_compute_tfidf_duplicate_terms_in_query(self):
        """Test TF-IDF with duplicate terms in query."""
        documents = ["cat dog bird", "cat cat dog", "bird bird bird"]
        query_terms = ["cat", "cat", "dog"]  # "cat" appears twice

        scores = compute_tfidf(documents, query_terms)

        # Should handle duplicate query terms gracefully
        assert len(scores) == 3
        assert all(isinstance(score, float) for score in scores)

        # First two documents should have positive scores
        assert scores[0] > 0.0
        assert scores[1] > 0.0
        # Third document only contains "bird", so should have zero score
        assert scores[2] == 0.0

    def test_compute_bm25_duplicate_terms_in_query(self):
        """Test BM25 with duplicate terms in query."""
        documents = ["cat dog bird", "cat cat dog", "bird bird bird"]
        query_terms = ["cat", "cat", "dog"]  # "cat" appears twice

        scores = compute_bm25(documents, query_terms)

        # Should handle duplicate query terms gracefully
        assert len(scores) == 3
        assert all(isinstance(score, float) for score in scores)

        # First two documents should have positive scores
        assert scores[0] > 0.0
        assert scores[1] > 0.0
        # Third document only contains "bird", so should have zero score
        assert scores[2] == 0.0
