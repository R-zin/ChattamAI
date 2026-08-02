"""Tests for ``app.rag.graph._parse_violations``.

NOTE (reconciliation): these pin the CURRENT best-effort parser. It strips only
leading/trailing backticks and an optional leading ``json`` fence tag, then does
``json.loads``; on any failure it returns ``[]`` *silently*. Agent-2's Phase-2
work replaces this with a tolerant extractor that finds the first ``{...}``
block and, on failure, sets ``ComplianceState.error`` instead of returning
``[]``. When that lands, the malformed/prose assertions below are expected to
change (documented per-test).
"""

from __future__ import annotations

import json

from app.rag.graph import _parse_violations

GOOD = {"violations": [{"rule_reference": "Rule 5", "severity": "high"}]}


def test_parses_plain_json_object():
    assert _parse_violations(json.dumps(GOOD)) == GOOD["violations"]


def test_strips_json_fence():
    fenced = "```json\n" + json.dumps(GOOD) + "\n```"
    assert _parse_violations(fenced) == GOOD["violations"]


def test_strips_bare_backtick_fence():
    fenced = "```\n" + json.dumps(GOOD) + "\n```"
    assert _parse_violations(fenced) == GOOD["violations"]


def test_malformed_json_returns_empty_silently():
    # CURRENT: malformed JSON -> [] (no error surfaced). Phase-2 flips this to
    # record a `parse_failed` error instead.
    assert _parse_violations('{"violations": [ {bad json,,, }') == []


def test_non_dict_top_level_returns_empty():
    assert _parse_violations("[1, 2, 3]") == []


def test_missing_violations_key_returns_empty():
    assert _parse_violations('{"other": 1}') == []


def test_empty_string_returns_empty():
    assert _parse_violations("") == []


def test_json_embedded_in_prose_not_recovered_currently():
    # CURRENT: the naive fence-strip cannot recover JSON embedded in prose, so
    # this returns [] today. Phase-2's tolerant extractor is expected to recover
    # the violations list here.
    body = "Analysis follows:\n" + json.dumps(GOOD) + "\nEnd of analysis."
    assert _parse_violations(body) == []
