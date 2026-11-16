"""Kerala Building Rules domain lexicon used by retrieval.

Three small, deterministic pieces of domain knowledge live here so retrieval can
be improved without another model call:

* ``tokenize`` - the lexical (BM25) tokenizer. Strips punctuation, keeps clause
  numbers such as ``5.3.1`` intact, separates a number from its unit
  (``1.8m`` -> ``1.8`` + ``metre``) and folds plurals / spelling variants so
  ``setbacks`` matches ``setback`` and ``meters`` matches ``metres``.
* ``expand_query_tokens`` - query-side synonym expansion. A plan says "front
  setback" while the gazetted rules say "yards" and "open spaces"; a plan says
  "FAR" while the rules say "floor space index".
* ``TOPICS`` - the regulated planning topics. Each topic knows how to recognise
  itself in an extracted fact line, which retrieval query finds its governing
  rule, and what textual evidence shows a rule excerpt actually covers it.

Everything is pure Python and offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Pattern, Tuple

# Words (letters/digits) with inner dots kept, so "5.3.1" and "sq.m" survive.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")
# A number glued to a unit: "1.8m", "12m", "240sqm".
_NUM_UNIT_RE = re.compile(r"^(\d+(?:\.\d+)?)([a-z][a-z.]*)$")
_DECIMAL_RE = re.compile(r"^\d+\.\d+$")

# Spelling / abbreviation variants folded onto one canonical token.
_VARIANTS: Dict[str, str] = {
    "meter": "metre",
    "m": "metre",
    "mt": "metre",
    "mts": "metre",
    "mtr": "metre",
    "story": "storey",
    "stories": "storey",
    "storeyed": "storey",
    "storied": "storey",
    "sq.m": "sqm",
    "sq.mt": "sqm",
    "sq.metre": "sqm",
    "sq.meter": "sqm",
    "sqmt": "sqm",
    "f.s.i": "fsi",
    "f.a.r": "far",
    "stairway": "staircase",
    "stair": "staircase",
    "setbacks": "setback",
}

_STOPWORD_LIST = """a an and are as at be by for from has have if in into is it its
of on or shall should than that the their there these this to was were what when
where which who will with within not no any all per each such may can do does
how much many minimum maximum required requirement rule rules""".split()


def normalize_token(token: str) -> str:
    """Fold one lower-cased token onto its canonical form."""
    token = _VARIANTS.get(token, token)
    if _DECIMAL_RE.match(token):
        # "3.0" and "3" are the same quantity; "1.50" and "1.5" too.
        token = token.rstrip("0").rstrip(".")
        return token or "0"
    if (
        len(token) > 3
        and token.endswith("s")
        and not token.endswith("ss")
        and token.isalpha()
    ):
        token = token[:-1]
    return _VARIANTS.get(token, token)


#: Stopwords in both raw and normalised form ("this" normalises to "thi").
STOPWORDS = frozenset(_STOPWORD_LIST) | frozenset(
    normalize_token(w) for w in _STOPWORD_LIST
)


def tokenize(text: str) -> List[str]:
    """Normalised lexical tokens for the BM25 index and overlap measures."""
    out: List[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        match = _NUM_UNIT_RE.match(raw)
        if match:
            out.append(normalize_token(match.group(1)))
            out.append(normalize_token(match.group(2).strip(".")))
            continue
        out.append(normalize_token(raw))
    return [t for t in out if t]


def content_tokens(text: str) -> List[str]:
    """Tokens with stopwords and bare punctuation-like fragments removed."""
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]


# --------------------------------------------------------------------------
# Query-side synonym expansion (lexical channel only)
# --------------------------------------------------------------------------
# (trigger on the raw query, tokens to add). "FAR" is matched case-sensitively
# because lower-case "far" is an ordinary English word.
_SYNONYM_RULES: Tuple[Tuple[Pattern[str], Tuple[str, ...]], ...] = (
    (
        re.compile(
            r"\b[Ff]\.?[Ss]\.?[Ii]\b|[Ff]loor [Ss]pace [Ii]ndex|\bFAR\b|\bF\.A\.R\b"
            r"|[Ff]loor [Aa]rea [Rr]atio"
        ),
        ("fsi", "far", "floor", "space", "index", "ratio"),
    ),
    (
        re.compile(r"set-?\s?backs?|open (?:air )?spaces?|\byards?\b", re.I),
        ("setback", "yard", "open", "space"),
    ),
    (re.compile(r"\bparking\b|car park|\bgarage\b", re.I), ("parking", "car")),
    (re.compile(r"stair", re.I), ("staircase",)),
    (
        re.compile(r"\bstoreys?\b|\bstor(?:y|ies)\b|\bfloors?\b", re.I),
        ("storey", "floor"),
    ),
    (re.compile(r"\broad\b|\bstreet\b", re.I), ("road", "street", "access")),
    (re.compile(r"\bcoverage\b|\bplinth\b", re.I), ("coverage", "plinth")),
    (re.compile(r"\bfire\b|\bescape\b", re.I), ("fire", "exit", "escape")),
    (re.compile(r"\bheight\b|\btall\b", re.I), ("height",)),
)


def expand_query_tokens(query: str, tokens: Optional[List[str]] = None) -> List[str]:
    """Tokens for ``query`` plus domain synonyms it implies.

    Used only on the lexical (BM25) side: the dense embedding already captures
    paraphrase, but BM25 cannot match "setback" against "yard" on its own.
    """
    base = list(tokens) if tokens is not None else tokenize(query)
    seen = set(base)
    for trigger, additions in _SYNONYM_RULES:
        if trigger.search(query):
            for token in additions:
                if token not in seen:
                    seen.add(token)
                    base.append(token)
    return base


# --------------------------------------------------------------------------
# Regulated planning topics
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Topic:
    key: str
    label: str
    # Recognises the topic in a fact line or a question.
    fact_pattern: Pattern[str]
    # Canonical retrieval query for the governing rule.
    query: str
    # Evidence that a rule excerpt covers the topic.
    evidence: Pattern[str]


def _topic(key: str, label: str, fact: str, query: str, evidence: str) -> Topic:
    return Topic(
        key=key,
        label=label,
        fact_pattern=re.compile(fact, re.I),
        query=query,
        evidence=re.compile(evidence, re.I),
    )


# Ordered by how often the topic decides a permit, which is also the order in
# which topics claim result slots when ``top_k`` is smaller than the topic count.
TOPICS: Tuple[Topic, ...] = (
    _topic(
        "setbacks",
        "Setbacks",
        r"set-?\s?back|open space|\byards?\b|side margin",
        "minimum front rear and side setback open space yard from plot boundary",
        r"set-?\s?backs?|open (?:air )?spaces?|\byards?\b",
    ),
    _topic(
        "fsi",
        "FSI / FAR",
        r"\bf\.?s\.?i\b|\bf\.?a\.?r\b|floor space|floor area ratio"
        r"|built-?\s?up area|builtup|total floor area",
        "maximum permissible floor space index FSI floor area ratio FAR "
        "total built-up area",
        r"floor space index|\bf\.?\s?s\.?\s?i\b|floor area ratio|\bf\.?a\.?r\b",
    ),
    _topic(
        "coverage",
        "Coverage",
        r"coverage|plinth|ground cover",
        "maximum permissible percentage of coverage ground coverage plinth area",
        r"\bcoverage\b|plinth area",
    ),
    _topic(
        "height",
        "Height & floors",
        r"height|\btall\b|\bfloors\b|number of floor|floor count|\d\s*-?\s*floor"
        r"|storey|stor(?:y|ies)\b",
        "maximum height of building number of floors storeys",
        r"height of (?:the |any |a )?buildings?|building height|maximum height"
        r"|number of (?:floors|storeys)|\bstoreys?\b",
    ),
    _topic(
        "parking",
        "Parking",
        r"parking|garage|car park",
        "off-street car parking spaces required",
        r"\bparking\b",
    ),
    _topic(
        "access",
        "Road access",
        r"\broad\b|\bstreet\b|\baccess\b",
        "access to building and plot, minimum width of access, width of road or "
        "street abutting the plot",
        r"\baccess\b[^.]{0,60}\b(?:width|road|street|plot|building)"
        r"|\b(?:width|road|street)\b[^.]{0,60}\baccess\b"
        r"|road width|street width|width of (?:the |any )?(?:road|street)"
        r"|abutting (?:the |a )?(?:road|street)",
    ),
    _topic(
        "fire_stair",
        "Fire safety & stairs",
        r"stair|\bfire\b|\bexits?\b|escape|\blift\b|elevator",
        "staircases and fire escape staircases, minimum width of staircase, "
        "fire safety and emergency exits",
        r"stair|fire escape|fire safety|fire protection|emergency exit"
        r"|travel distance|exit width",
    ),
    _topic(
        "plot",
        "Plot area",
        r"plot area|plot size|site area|land area|\bextent\b|\bcents?\b",
        "minimum plot area plot size small plots",
        r"plot area|area of (?:the )?plot|minimum plot|small plots?|plot size"
        r"|extent of (?:the )?(?:plot|land)",
    ),
    _topic(
        "occupancy",
        "Occupancy",
        r"occupancy|usage|use type|building type|purpose",
        "occupancy classification of buildings occupancy group",
        r"occupancy (?:classification|group)|occupanc\w*[^.]{0,50}classif"
        r"|classif\w*[^.]{0,50}occupanc|occupancy of buildings",
    ),
)

TOPICS_BY_KEY: Dict[str, Topic] = {t.key: t for t in TOPICS}

_UNSPECIFIED_RE = re.compile(
    r"^\s*(?:not (?:specified|stated|mentioned|provided|given|available|applicable)"
    r"|unspecified|unknown|n/?a|none|nil|-+)?\s*\.?\s*$",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")


@dataclass(frozen=True)
class Fact:
    parameter: str
    value: str
    topics: Tuple[str, ...]


def parse_facts(text: str) -> List[Fact]:
    """Parse ``- parameter: value`` lines into facts tagged with their topics.

    Lines whose value is "not specified" (or similar) are dropped: there is no
    plan value to check, so no rule needs retrieving for them.
    """
    facts: List[Fact] = []
    for line in (text or "").splitlines():
        line = _BULLET_RE.sub("", line).strip()
        if not line:
            continue
        if ":" in line:
            parameter, value = line.split(":", 1)
        else:
            parameter, value = line, ""
        parameter = parameter.strip()
        value = value.strip()
        if ":" in line and _UNSPECIFIED_RE.match(value):
            continue
        topics = tuple(t.key for t in TOPICS if t.fact_pattern.search(parameter))
        if not topics:
            # Free-text lines ("3 floor building, 12m tall") have no
            # "parameter:" structure, or carry the topic on the value side.
            topics = tuple(t.key for t in TOPICS if t.fact_pattern.search(line))
        facts.append(Fact(parameter=parameter, value=value, topics=topics))
    return facts


def detect_topics(text: str) -> List[Topic]:
    """Topics mentioned anywhere in free text (a question or a plan summary)."""
    return [t for t in TOPICS if t.fact_pattern.search(text or "")]
