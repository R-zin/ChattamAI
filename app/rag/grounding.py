"""Citation grounding: does each finding cite a rule that was actually retrieved?

The analysis model is told to cite only the excerpts it was given, but nothing
enforced that: a finding could quote "Rule 23(4)" when no such rule was in the
prompt, or state a required value that appears in no excerpt. This module checks
both, deterministically, after the model has answered:

* **Citation** - the rule identifier in ``rule_reference`` is resolved against
  the retrieved excerpts (their ``rule_id``, heading breadcrumb and body text).
* **Value** - the numbers in ``required_value`` are looked up in the cited
  excerpts (``3.0 m`` matches ``3 metres``).

Each finding gets a status:

* ``grounded``   - the cited rule was retrieved and supports the required value
* ``partial``    - one of the two holds, not both
* ``ungrounded`` - the reference names a rule that was not retrieved
* ``uncited``    - the reference names no identifiable rule at all

Nothing is deleted. Grounding is evidence for the reviewer, not a verdict: an
ungrounded finding may still be right, it just cannot be checked against the
retrieved text.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

Hit = Tuple[str, dict, float]

# "23(4)", "5.3.1", "26", "12A" - a rule number with optional sub-rule parts.
_RULE_NUM_RE = re.compile(r"\d+[A-Za-z]?(?:\.\d+)*(?:\s*\(\w+\))*")
_TABLE_RE = re.compile(r"\btable\s*(\d+[A-Za-z]?)", re.I)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
# Dotted clause identifiers are labels, not quantities.
_CLAUSE_ID_RE = re.compile(r"\b\d+(?:\.\d+){2,}\b")
# Years and similar: "KPBR 2019" is not a rule number.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _base(identifier: str) -> str:
    """``"23(4)"`` -> ``"23"``; ``"5.3.1"`` stays ``"5.3.1"``."""
    return re.split(r"\s*\(", identifier, maxsplit=1)[0].strip().lower()


def extract_rule_identifiers(reference: str) -> Dict[str, List[str]]:
    """Rule numbers and table numbers named in a ``rule_reference`` string."""
    text = _YEAR_RE.sub(" ", reference or "")
    tables = [m.group(1).lower() for m in _TABLE_RE.finditer(text)]
    text = _TABLE_RE.sub(" ", text)
    rules: List[str] = []
    for match in _RULE_NUM_RE.finditer(text):
        base = _base(match.group(0))
        if base and base not in rules:
            rules.append(base)
    return {"rules": rules, "tables": tables}


def _hit_rule_bases(meta: dict) -> List[str]:
    """Rule numbers a retrieved chunk is filed under (from ``rule_id``)."""
    rule_id = str(meta.get("rule_id") or "")
    if "#chunk-" in rule_id:
        return []
    ids = extract_rule_identifiers(rule_id)
    return ids["rules"]


def _mentions_rule(text: str, base: str) -> bool:
    """Whether ``text`` contains ``base`` as a rule/clause identifier."""
    escaped = re.escape(base)
    if "." in base:
        # A dotted clause id is specific enough to match on its own.
        return re.search(rf"(?<![\d.]){escaped}(?![\d])", text) is not None
    # A bare integer only counts when introduced as a rule ("Rule 26",
    # "Section 5") or as a clause prefix ("26(1)", or "5.3 Setbacks" - a
    # clause number is followed by a capitalised word, a quantity such as
    # "5.5 metres" is not).
    return (
        re.search(
            rf"\b(?:rules?|section|sec\.?|clause|regulation)\s*{escaped}\b",
            text,
            re.I,
        )
        is not None
        or re.search(rf"(?<![\d.]){escaped}(?:\(\d+\)|(?:\.\d+)+\s+[A-Z(])", text)
        is not None
    )


def _numbers(text: str) -> List[float]:
    cleaned = _CLAUSE_ID_RE.sub(" ", text or "")
    out: List[float] = []
    for raw in _NUMBER_RE.findall(cleaned):
        try:
            out.append(float(raw))
        except ValueError:  # pragma: no cover - regex guarantees a float
            continue
    return out


def _cites(hit: Hit, ids: Dict[str, List[str]]) -> bool:
    text, meta, _score = hit
    haystack = f"{meta.get('section') or ''}\n{text}"
    rule_id = str(meta.get("rule_id") or "")
    hit_bases = _hit_rule_bases(meta)
    hit_tables = [m.group(1).lower() for m in _TABLE_RE.finditer(rule_id)]
    for base in ids["rules"]:
        # "5.3.1" is grounded by a chunk filed under "5.3" that contains it.
        if base in hit_bases or _mentions_rule(haystack, base):
            return True
    for table in ids["tables"]:
        if table in hit_tables or re.search(
            rf"\btable\s*{re.escape(table)}\b", haystack, re.I
        ):
            return True
    return False


def ground_violation(violation: Dict[str, Any], retrieved: Sequence[Hit]) -> dict:
    """Grounding record for one finding against the retrieved excerpts."""
    reference = str(violation.get("rule_reference") or "")
    ids = extract_rule_identifiers(reference)
    has_identifier = bool(ids["rules"] or ids["tables"])
    citations = [idx for idx, hit in enumerate(retrieved, start=1) if _cites(hit, ids)]

    required = _numbers(str(violation.get("required_value") or ""))
    value_supported: Optional[bool] = None
    value_citations: List[int] = []
    if required:
        pool = citations or list(range(1, len(retrieved) + 1))
        for idx in pool:
            present = set(_numbers(retrieved[idx - 1][0]))
            if all(value in present for value in required):
                value_citations.append(idx)
        value_supported = bool(value_citations)

    if citations and value_supported is not False:
        status = "grounded"
        note = "Cited rule was retrieved" + (
            " and states the required value." if value_supported else "."
        )
    elif citations:
        status = "partial"
        note = "Cited rule was retrieved, but it does not state the required value."
    elif value_supported:
        # The number is in the retrieved text, under a different rule label.
        status = "partial"
        citations = value_citations
        note = (
            "The required value appears in the retrieved rules, but not under "
            "the rule this finding cites."
        )
    elif has_identifier:
        status = "ungrounded"
        note = "The cited rule is not among the retrieved excerpts."
    else:
        status = "uncited"
        note = "The finding does not name an identifiable rule."

    return {
        "rule_reference": reference,
        "status": status,
        "citations": citations,
        "value_supported": value_supported,
        "note": note,
    }


def ground_violations(
    violations: Sequence[Dict[str, Any]], retrieved: Sequence[Hit]
) -> dict:
    """Ground every finding; returns per-finding records and a summary.

    ``score`` is the share of findings that can be checked against the
    retrieved text (a partial counts half); ``1.0`` when there are no findings.
    """
    items = []
    for index, violation in enumerate(violations or []):
        if not isinstance(violation, dict):
            continue
        record = ground_violation(violation, retrieved)
        record["violation_index"] = index
        items.append(record)

    counts = {"grounded": 0, "partial": 0, "ungrounded": 0, "uncited": 0}
    for record in items:
        counts[record["status"]] += 1
    total = len(items)
    score = (
        round((counts["grounded"] + 0.5 * counts["partial"]) / total, 3)
        if total
        else 1.0
    )
    return {"total": total, "score": score, **counts, "items": items}
