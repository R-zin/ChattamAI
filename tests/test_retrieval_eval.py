"""Retrieval quality gate on the bundled rulebook.

Runs the golden cases (``tests/fixtures/retrieval_golden.json``) through the
offline evaluation harness (``scripts/eval_retrieval.py``) against the real
corpus in ``data/kbr`` - the sample excerpt and the 179-page Kerala Panchayat
Building Rules gazette. Asserts that the shipped configuration (structure-aware
chunks + the topic-aware retriever) finds the governing rule, and that it is
not worse than the previous pipeline (flat chunks + one hybrid query).

The embedder is a deterministic hashed bag-of-words, so this measures chunking,
query decomposition and fusion - not a real embedding model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import eval_retrieval  # noqa: E402


@pytest.fixture(scope="module")
def reports():
    out = eval_retrieval.run(top_k=8)
    return {(r["index"], r["strategy"]): r for r in out}


def test_golden_set_is_well_formed():
    cases = eval_retrieval.load_golden()
    assert len(cases) >= 12
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert case["kind"] in {"facts", "question"}
        assert case["expect"] and all(e["rules"] for e in case["expect"])


def test_shipped_configuration_finds_the_governing_rules(reports):
    shipped = reports[("structured", "advanced")]
    assert shipped["recall"] >= 0.9, shipped["rows"]
    assert shipped["mrr"] >= 0.75
    assert shipped["full_coverage"] >= 0.85


def test_shipped_configuration_beats_the_previous_pipeline(reports):
    shipped = reports[("structured", "advanced")]
    previous = reports[("flat", "simple")]
    assert shipped["recall"] > previous["recall"]
    assert shipped["mrr"] > previous["mrr"]


def test_topic_aware_retrieval_helps_on_a_structured_index(reports):
    advanced = reports[("structured", "advanced")]
    simple = reports[("structured", "simple")]
    assert advanced["recall"] > simple["recall"]


def test_every_direct_question_finds_its_rule(reports):
    shipped = reports[("structured", "advanced")]
    missed = [
        row["id"]
        for row in shipped["rows"]
        if row["id"].startswith("q-") and row["missed"]
    ]
    assert missed == []


def test_rule_base_normalisation():
    assert eval_retrieval._rule_base("Rule 26, Table 4") == "rule 26"
    assert eval_retrieval._rule_base("Rule 26(4)") == "rule 26"
    assert eval_retrieval._rule_base("5.3") == "5.3"
    assert eval_retrieval._rule_base(None) == ""


def test_cli_prints_a_table(capsys, tmp_path):
    # A corpus of just the sample excerpt keeps the CLI smoke test fast.
    sample = ROOT / "data" / "kbr" / "sample_kbr_excerpt.txt"
    (tmp_path / sample.name).write_text(sample.read_text(encoding="utf-8"))
    args = ["--corpus", str(tmp_path), "--cases", "q-parking", "--top-k", "4", "-v"]
    assert eval_retrieval.main(args) == 0
    out = capsys.readouterr().out
    assert "recall@k" in out
    assert "structured  advanced" in out
    assert "q-parking" in out


def test_cli_json_output(capsys, tmp_path):
    import json

    sample = ROOT / "data" / "kbr" / "sample_kbr_excerpt.txt"
    (tmp_path / sample.name).write_text(sample.read_text(encoding="utf-8"))
    args = ["--corpus", str(tmp_path), "--cases", "q-parking", "--json"]
    assert eval_retrieval.main(args) == 0
    reports = json.loads(capsys.readouterr().out)
    assert {(r["index"], r["strategy"]) for r in reports} == {
        ("flat", "simple"),
        ("flat", "advanced"),
        ("structured", "simple"),
        ("structured", "advanced"),
    }
    assert all(r["recall"] == 1.0 for r in reports)
