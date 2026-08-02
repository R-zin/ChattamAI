"""Tests for ``app.rag.prompts.format_rules_for_prompt`` and helpers."""

from __future__ import annotations

from app.rag.prompts import build_analyze_user, format_rules_for_prompt


def test_numbering_starts_at_one():
    rules = [
        ("alpha", {"source": "a.txt", "rule_id": "Rule 1"}, 0.1),
        ("beta", {"source": "b.txt", "rule_id": "Rule 2"}, 0.2),
    ]
    out = format_rules_for_prompt(rules)
    lines = out.splitlines()
    assert lines[0].startswith("[1] ")
    assert "[2] " in out


def test_source_and_rule_id_rendered():
    rules = [("the rule body", {"source": "kbr.txt", "rule_id": "Rule 5"}, 0.12)]
    out = format_rules_for_prompt(rules)
    assert out == "[1] (kbr.txt / Rule 5)\nthe rule body"


def test_falls_back_to_chunk_then_index_for_rule_id():
    rules = [
        ("c", {"source": "s.txt", "chunk": 7}, 0.0),  # no rule_id -> chunk
        ("d", {"source": "s.txt"}, 0.0),  # neither -> 1-based index
    ]
    out = format_rules_for_prompt(rules)
    assert "[1] (s.txt / 7)\nc" in out
    assert "[2] (s.txt / 2)\nd" in out


def test_missing_source_defaults_to_unknown():
    rules = [("body", {"rule_id": "Rule 9"}, 0.0)]
    assert format_rules_for_prompt(rules).startswith("[1] (unknown / Rule 9)")


def test_entries_joined_with_blank_line():
    rules = [
        ("one", {"source": "s", "rule_id": "A"}, 0.0),
        ("two", {"source": "s", "rule_id": "B"}, 0.0),
    ]
    out = format_rules_for_prompt(rules)
    assert "\n\n" in out


def test_empty_rules_returns_empty_string():
    assert format_rules_for_prompt([]) == ""


def test_build_analyze_user_interpolates_facts_and_rules():
    out = build_analyze_user("FACTS-HERE", "RULES-HERE")
    assert "FACTS-HERE" in out
    assert "RULES-HERE" in out
    assert "EXTRACTED PLAN FACTS" in out
    assert "RETRIEVED KERALA BUILDING RULE EXCERPTS" in out
