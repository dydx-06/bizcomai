import numpy as np
import pytest

from app.embeddings import HashingEmbedder, StubEmbedder, cosine_similarity


def test_cosine_identical_vectors_is_one():
    v = np.array([[1.0, 2.0, 3.0]])
    assert cosine_similarity(v, v)[0][0] == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_zero():
    a = np.array([[1.0, 0.0]])
    b = np.array([[0.0, 1.0]])
    assert cosine_similarity(a, b)[0][0] == pytest.approx(0.0)


def test_cosine_handles_zero_vector_without_nan():
    """A zero vector must not poison the matrix with nan."""
    a = np.array([[0.0, 0.0]])
    b = np.array([[1.0, 1.0]])
    result = cosine_similarity(a, b)
    assert not np.isnan(result).any()


def test_cosine_returns_full_matrix_shape():
    a = np.random.rand(3, 8)
    b = np.random.rand(5, 8)
    assert cosine_similarity(a, b).shape == (3, 5)


def test_hashing_embedder_is_deterministic():
    e = HashingEmbedder(dim=64)
    assert np.array_equal(e.encode(["gst payment"]), e.encode(["gst payment"]))


def test_hashing_embedder_is_case_insensitive():
    e = HashingEmbedder(dim=64)
    assert np.array_equal(e.encode(["GST Payment"]), e.encode(["gst payment"]))


def test_hashing_embedder_respects_dimension():
    assert HashingEmbedder(dim=128).encode(["a", "b"]).shape == (2, 128)


def test_hashing_embedder_similar_strings_score_higher_than_dissimilar():
    e = HashingEmbedder(dim=512)
    vecs = e.encode(["electricity bill payment", "electricity bill paid", "purchase of steel rods"])
    sims = cosine_similarity(vecs[0:1], vecs[1:])[0]
    assert sims[0] > sims[1]


def test_stub_embedder_raises_on_unknown_text():
    """Guards against a test silently passing on an undefined input."""
    stub = StubEmbedder({"known": [1.0, 0.0]})
    with pytest.raises(KeyError, match="no vector"):
        stub.encode(["unknown"])
