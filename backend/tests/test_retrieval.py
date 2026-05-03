from backend.app.retrieval import cosine_similarity, hash_embedding, hybrid_score, tag_overlap


def test_hash_embedding_deterministic():
    vec1 = hash_embedding("test case")
    vec2 = hash_embedding("test case")
    assert vec1 == vec2
    assert len(vec1) == 256


def test_cosine_similarity():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_tag_overlap():
    assert tag_overlap(["a", "b"], ["b", "c"]) == 1 / 3


def test_hybrid_score():
    score = hybrid_score(0.8, 0.4)
    assert 0.5 < score < 0.9
