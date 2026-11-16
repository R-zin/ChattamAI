"""Tests for the KBR domain lexicon (``app.rag.lexicon``): the lexical tokenizer,
query-side synonym expansion, fact parsing and topic detection. Pure Python."""

from __future__ import annotations

from app.rag.lexicon import (
    TOPICS,
    TOPICS_BY_KEY,
    content_tokens,
    detect_topics,
    expand_query_tokens,
    parse_facts,
    tokenize,
)


# -- tokenizer ---------------------------------------------------------------
def test_tokenize_strips_punctuation():
    assert tokenize("setback, (FSI); parking.") == ["setback", "fsi", "parking"]


def test_tokenize_keeps_clause_numbers_intact():
    assert "5.3.1" in tokenize("Clause 5.3.1 applies.")


def test_tokenize_separates_number_from_unit():
    assert tokenize("1.8m") == ["1.8", "metre"]
    assert tokenize("12m tall") == ["12", "metre", "tall"]


def test_tokenize_folds_plurals_and_spelling_variants():
    assert tokenize("setbacks") == tokenize("setback")
    assert tokenize("meters") == tokenize("metres") == ["metre"]
    assert tokenize("storeys") == tokenize("stories") == ["storey"]
    assert tokenize("F.S.I.") == ["fsi"]


def test_tokenize_normalises_trailing_zero_decimals():
    # "3.0 metres" in a rule must match "3 m" in a finding.
    assert tokenize("3.0 metres") == tokenize("3 m") == ["3", "metre"]


def test_tokenize_does_not_strip_double_s_words():
    assert tokenize("access") == ["access"]


def test_content_tokens_drops_stopwords():
    tokens = content_tokens("What is the minimum front setback for this building?")
    assert tokens == ["front", "setback", "building"]


# -- synonym expansion -------------------------------------------------------
def test_setback_query_expands_to_the_rulebook_vocabulary():
    # The gazetted rules say "yards" / "open spaces", plans say "setback".
    tokens = expand_query_tokens("front setback")
    assert {"setback", "yard", "open", "space"} <= set(tokens)


def test_far_expands_only_when_it_is_the_acronym():
    assert "fsi" in expand_query_tokens("maximum FAR for a house")
    assert "fsi" in expand_query_tokens("floor area ratio limit")
    # Ordinary English "far" must not drag FSI vocabulary into the query.
    assert "fsi" not in expand_query_tokens("how far from the road")


def test_expansion_never_duplicates_tokens():
    tokens = expand_query_tokens("setback yard open space")
    assert len(tokens) == len(set(tokens))


def test_query_without_domain_terms_is_unchanged():
    assert expand_query_tokens("hello world") == ["hello", "world"]


# -- fact parsing ------------------------------------------------------------
FACTS = (
    "- plot area: 300 sq.m\n"
    "- number of floors: 3\n"
    "- building height: 12m\n"
    "- front setback: 1m\n"
    "- floor space index (FSI): 1.5\n"
    "- parking provision: not specified\n"
    "- road width abutting the plot: 4m\n"
    "- occupancy/usage type: residential"
)


def test_parse_facts_tags_each_line_with_its_topic():
    facts = {f.parameter: f.topics for f in parse_facts(FACTS)}
    assert facts["plot area"] == ("plot",)
    assert facts["number of floors"] == ("height",)
    assert facts["building height"] == ("height",)
    assert facts["front setback"] == ("setbacks",)
    assert facts["floor space index (FSI)"] == ("fsi",)
    assert facts["road width abutting the plot"] == ("access",)
    assert facts["occupancy/usage type"] == ("occupancy",)


def test_parse_facts_drops_unspecified_values():
    # No plan value means nothing to check, so no rule needs retrieving.
    assert "parking provision" not in {f.parameter for f in parse_facts(FACTS)}
    assert parse_facts("- staircase: N/A\n- lift: none\n- fire exit:") == []


def test_parse_facts_handles_free_text_lines():
    (fact,) = parse_facts("3 floor building, 12m tall, 1m front setback")
    assert set(fact.topics) == {"setbacks", "height"}


def test_floor_space_index_is_not_mistaken_for_a_floor_count():
    (fact,) = parse_facts("- floor space index: 1.5")
    assert fact.topics == ("fsi",)


def test_parse_facts_accepts_numbered_and_starred_bullets():
    facts = parse_facts("1. front setback: 2m\n* parking: 2 cars")
    assert [f.parameter for f in facts] == ["front setback", "parking"]


def test_parse_facts_empty_input():
    assert parse_facts("") == []
    assert parse_facts(None) == []


# -- topics ------------------------------------------------------------------
def test_detect_topics_in_a_question():
    keys = [t.key for t in detect_topics("How many car parking spaces are needed?")]
    assert keys == ["parking"]


def test_every_topic_recognises_its_own_canonical_query_as_evidence():
    # A topic's retrieval query must look like evidence of that topic, or the
    # coverage grader could never be satisfied by an on-topic rule.
    for topic in TOPICS:
        assert topic.evidence.search(topic.query), topic.key


def test_topic_keys_are_unique():
    assert len(TOPICS_BY_KEY) == len(TOPICS)


def test_evidence_patterns_do_not_fire_on_unrelated_text():
    text = "The Secretary shall issue the permit within thirty days."
    assert [t.key for t in TOPICS if t.evidence.search(text)] == []
