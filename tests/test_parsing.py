"""Tests for ``app.rag.graph._parse_violations``.

CURRENT (optimized) contract — agent-2 replaced the old silent best-effort
parser. ``_parse_violations`` now returns a ``(violations, error)`` tuple:
- success -> ``(violations, None)``
- failure -> ``([], "parse_failed: ...")`` so the caller can surface the problem
  instead of silently returning zero violations.
Extraction is tolerant (``_extract_json``): a leading ``` json fence is stripped
and, failing a whole-string parse, the first balanced ``{...}`` block in the
text is recovered — so JSON embedded in prose now parses. These tests pin the
NEW behaviour (verified against the merged code, not assumed).
"""

from __future__ import annotations

import json

from app.rag.graph import _parse_violations

GOOD = {"violations": [{"rule_reference": "Rule 5", "severity": "high"}]}


def test_plain_json_object_returns_tuple_with_no_error():
    assert _parse_violations(json.dumps(GOOD)) == (GOOD["violations"], None)


def test_json_fence_is_parsed():
    fenced = "```json\n" + json.dumps(GOOD) + "\n```"
    assert _parse_violations(fenced) == (GOOD["violations"], None)


def test_bare_backtick_fence_is_parsed():
    fenced = "```\n" + json.dumps(GOOD) + "\n```"
    assert _parse_violations(fenced) == (GOOD["violations"], None)


def test_json_embedded_in_prose_is_recovered():
    # NEW: the balanced-brace extractor recovers the object inside prose.
    body = "Analysis follows:\n" + json.dumps(GOOD) + "\nEnd of analysis."
    assert _parse_violations(body) == (GOOD["violations"], None)


def test_unparseable_text_returns_error_not_silent_empty():
    violations, error = _parse_violations("not json at all")
    assert violations == []
    assert error is not None
    assert error.startswith("parse_failed")


def test_error_message_contains_input_snippet():
    _v, error = _parse_violations("not json at all")
    assert "not json at all" in error


def test_malformed_json_object_returns_error_not_silent_empty():
    # Invalid JSON with a brace that can't be parsed -> error (NOT silent []).
    violations, error = _parse_violations('{"violations": [ {bad json,,, }')
    assert violations == []
    assert error is not None and error.startswith("parse_failed")


def test_non_dict_top_level_returns_error():
    # A bare JSON array is valid JSON but not an object -> no violations object.
    violations, error = _parse_violations("[1, 2, 3]")
    assert violations == []
    assert error is not None and error.startswith("parse_failed")


def test_missing_violations_key_returns_empty_without_error():
    # Valid object but no "violations" key -> empty list, no error.
    assert _parse_violations('{"other": 1}') == ([], None)


def test_violations_not_a_list_returns_error():
    violations, error = _parse_violations('{"violations": {"x": 1}}')
    assert violations == []
    assert error is not None and error.startswith("parse_failed")


def test_empty_string_returns_error():
    violations, error = _parse_violations("")
    assert violations == []
    assert error is not None and error.startswith("parse_failed")
