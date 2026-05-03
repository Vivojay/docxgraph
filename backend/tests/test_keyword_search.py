from backend.app.services.keyword_search import bm25_lite_score, fuzzy_ratio, keyword_overlap_score, normalize_scores


def test_keyword_scores_reward_overlap():
    relevant = "acute facial droop with stroke concern and teleneuro consult"
    unrelated = "chronic dermatology follow up for eczema management"
    query = "stroke facial droop"

    assert bm25_lite_score(query, relevant) > bm25_lite_score(query, unrelated)
    assert keyword_overlap_score(query, relevant) > keyword_overlap_score(query, unrelated)
    assert fuzzy_ratio(query, relevant) > 0


def test_normalize_scores_handles_uniform_lists():
    assert normalize_scores([0.0, 0.0]) == [0.0, 0.0]
    assert normalize_scores([2.0, 2.0]) == [1.0, 1.0]
