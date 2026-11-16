"""Rulebook question answering: a cited answer, or an honest "not found".

``POST /api/rules/ask`` lets a user ask the indexed Kerala Building Rules a
direct question ("what is the minimum front setback for a house?") instead of
running a whole plan through the compliance pipeline. The answer is grounded:

1. The question is retrieved with the same topic-aware retriever the compliance
   check uses (app/rag/retrieval.py), so "setback" finds rules worded as "yards".
2. The model may answer **only** from the numbered excerpts and must cite each
   claim as ``[n]``. If the excerpts do not answer the question it must reply
   with the sentinel ``NOT_FOUND`` - it is not allowed to fall back on what it
   "knows" about building rules.
3. The citations are then verified here, not trusted: markers that point at no
   excerpt are stripped, and the answer's support level is derived from what
   survives.

``confidence`` is therefore a statement about evidence, not a model's feeling:

* ``high``   - cited, and the cited excerpts share the question's key terms
* ``medium`` - cited, but the cited excerpts use different wording
* ``low``    - the model answered without a single valid citation
* ``none``   - abstained (nothing retrieved, or the excerpts do not answer it)
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from app.rag.lexicon import content_tokens

Hit = Tuple[str, dict, float]

NOT_FOUND = "NOT_FOUND"

SYSTEM_QA = (
    "You are a reference assistant for the Kerala Building Rules. You will "
    "receive a QUESTION and numbered EXCERPTS retrieved from the indexed rules. "
    "Answer the question using ONLY the excerpts. Rules:\n"
    "1. Cite the excerpt that supports each statement with its number in square "
    "brackets, e.g. [2]. Every factual statement needs a citation.\n"
    "2. Quote figures (distances, areas, ratios, counts) exactly as written in "
    "the excerpt, with their units and any condition attached to them "
    "(occupancy group, building height, plot size).\n"
    "3. If the excerpts do not contain the answer, reply with exactly "
    f"{NOT_FOUND} and nothing else. Do not answer from general knowledge and "
    "do not guess.\n"
    "4. If the excerpts answer only part of the question, answer that part and "
    "say plainly what they do not cover.\n"
    "5. Be concise: at most six sentences, plain prose, no headings."
)

PROMPT_QA_USER = "QUESTION:\n{question}\n\nEXCERPTS:\n{rules}\n\nAnswer now."

ABSTAIN_EMPTY_INDEX = (
    "The rule index is empty, so there is nothing to answer from. Ingest the "
    "Kerala Building Rules documents and ask again."
)
ABSTAIN_NO_EVIDENCE = (
    "The indexed rules do not appear to answer this question. Try rephrasing "
    "it, or check that the relevant rule document has been ingested."
)

_CITATION_RE = re.compile(r"\[(\d{1,2})\]")
_MAX_QUESTION_CHARS = 600


def validate_question(question: str) -> str:
    """Trimmed question, or ``ValueError`` when it is empty / far too long."""
    cleaned = " ".join((question or "").split())
    if len(cleaned) < 3:
        raise ValueError("Ask a question of at least a few words.")
    if len(cleaned) > _MAX_QUESTION_CHARS:
        raise ValueError(
            f"Question is too long (limit {_MAX_QUESTION_CHARS} characters)."
        )
    return cleaned


def _citations_in(answer: str, count: int) -> List[int]:
    """Valid, de-duplicated excerpt numbers cited in ``answer`` (1-based)."""
    cited: List[int] = []
    for raw in _CITATION_RE.findall(answer):
        number = int(raw)
        if 1 <= number <= count and number not in cited:
            cited.append(number)
    return cited


def _strip_invalid_citations(answer: str, count: int) -> str:
    """Remove ``[n]`` markers that point at no excerpt."""

    def _keep(match: "re.Match[str]") -> str:
        return match.group(0) if 1 <= int(match.group(1)) <= count else ""

    return re.sub(r"[ \t]+([.,;])", r"\1", _CITATION_RE.sub(_keep, answer)).strip()


def _term_support(question: str, excerpts: Sequence[str]) -> float:
    """Share of the question's content terms present in the cited excerpts."""
    terms = set(content_tokens(question))
    if not terms:
        return 0.0
    present = set()
    for excerpt in excerpts:
        present.update(content_tokens(excerpt))
    return len(terms & present) / len(terms)


def _citation_payload(hits: Sequence[Hit], cited: Sequence[int]) -> List[dict]:
    out = []
    for number, (text, meta, score) in enumerate(hits, start=1):
        out.append(
            {
                "index": number,
                "cited": number in cited,
                "source": meta.get("source", ""),
                "rule_id": meta.get("rule_id"),
                "section": meta.get("section"),
                "page": meta.get("page"),
                "excerpt": text,
                "score": round(float(score), 4),
            }
        )
    return out


def answer_question(
    llm,
    retriever,
    question: str,
    top_k: int = 6,
    index_size: Optional[int] = None,
) -> dict:
    """Answer ``question`` from the rule index with verified citations."""
    from app.rag.prompts import format_rules_for_prompt

    question = validate_question(question)
    hits, trace = retriever.retrieve(question, k=top_k, facts_mode=False)
    base = {"question": question, "retrieval": trace.as_dict()}

    if not hits:
        empty = index_size == 0 if index_size is not None else False
        return {
            **base,
            "answer": ABSTAIN_EMPTY_INDEX if empty else ABSTAIN_NO_EVIDENCE,
            "abstained": True,
            "confidence": "none",
            "citations": [],
        }

    user = PROMPT_QA_USER.format(question=question, rules=format_rules_for_prompt(hits))
    raw = (llm.complete(SYSTEM_QA, user) or "").strip()

    if not raw or NOT_FOUND in raw.upper().replace(" ", "_"):
        return {
            **base,
            "answer": ABSTAIN_NO_EVIDENCE,
            "abstained": True,
            "confidence": "none",
            "citations": _citation_payload(hits, []),
        }

    cited = _citations_in(raw, len(hits))
    answer = _strip_invalid_citations(raw, len(hits))
    if not cited:
        confidence = "low"
    else:
        support = _term_support(question, [hits[n - 1][0] for n in cited])
        confidence = "high" if support >= 0.5 else "medium"
    return {
        **base,
        "answer": answer,
        "abstained": False,
        "confidence": confidence,
        "citations": _citation_payload(hits, cited),
    }
