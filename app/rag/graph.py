"""LangGraph workflow that turns a building plan into a compliance report.

Flow:
    extract_facts -> retrieve -> analyze -> summarize
                              |
                              +--> (no rules found) -> insufficient -> END

Nodes are plain functions closed over a `Context` so the graph stays easy to
test and the LLM / vector store can be swapped independently.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from typing import List, Optional, Tuple, TypedDict

from langgraph.graph import END, StateGraph


class ComplianceState(TypedDict, total=False):
    plan_text: str
    top_k: int
    facts: str
    retrieved: List[Tuple[str, dict, float]]
    analysis_json: str
    violations: List[dict]
    summary: str
    error: Optional[str]


@dataclass
class Context:
    llm: object  # ClaudeClient
    store: object  # RuleVectorStore
    default_top_k: int = 6


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------
def extract_facts(state: ComplianceState, ctx: Context) -> dict:
    from app.rag.prompts import SYSTEM_EXTRACT

    facts = ctx.llm.complete(SYSTEM_EXTRACT, state["plan_text"])
    return {"facts": facts}


def retrieve(state: ComplianceState, ctx: Context) -> dict:
    # Embed the extracted facts as the retrieval query for best semantic match.
    query = state.get("facts") or state["plan_text"]
    k = state.get("top_k") or ctx.default_top_k
    results = ctx.store.similarity_search(query, k=k)
    return {"retrieved": results}


def analyze(state: ComplianceState, ctx: Context) -> dict:
    from app.rag.prompts import (
        SYSTEM_ANALYZE,
        build_analyze_user,
        format_rules_for_prompt,
    )

    rules_text = format_rules_for_prompt(state["retrieved"])
    user = build_analyze_user(state["facts"], rules_text)
    raw = ctx.llm.complete(SYSTEM_ANALYZE, user)
    violations = _parse_violations(raw)
    return {"analysis_json": raw, "violations": violations}


def summarize(state: ComplianceState, ctx: Context) -> dict:
    from app.rag.prompts import SYSTEM_SUMMARY

    facts = state.get("facts", "")
    violations = state.get("violations") or []
    user = f"EXTRACTED FACTS:\n{facts}\n\nPOTENTIAL VIOLATIONS:\n{json.dumps(violations, indent=2)}"
    summary = ctx.llm.complete(SYSTEM_SUMMARY, user)
    return {"summary": summary}


def insufficient(state: ComplianceState, ctx: Context) -> dict:
    return {
        "summary": (
            "No relevant Kerala Building Rules could be retrieved for this plan. "
            "The rule index may be empty or not yet ingested. Please ingest the "
            "Kerala Building Rules documents and retry."
        ),
        "violations": [],
    }


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------
def route_retrieve(state: ComplianceState) -> str:
    if state.get("retrieved"):
        return "analyze"
    return "insufficient"


def _parse_violations(raw: str) -> List[dict]:
    """Best-effort parse of the JSON the analyzer is instructed to return."""
    try:
        # Strip markdown fences if the model added them.
        cleaned = raw.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        data = json.loads(cleaned)
        return data.get("violations", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, ValueError):
        return []


# --------------------------------------------------------------------------
# Graph builder
# --------------------------------------------------------------------------
def build_compliance_graph(ctx: Context):
    builder = StateGraph(ComplianceState)
    builder.add_node("extract_facts", partial(extract_facts, ctx=ctx))
    builder.add_node("retrieve", partial(retrieve, ctx=ctx))
    builder.add_node("analyze", partial(analyze, ctx=ctx))
    builder.add_node("summarize", partial(summarize, ctx=ctx))
    builder.add_node("insufficient", partial(insufficient, ctx=ctx))

    builder.set_entry_point("extract_facts")
    builder.add_edge("extract_facts", "retrieve")
    builder.add_conditional_edges(
        "retrieve",
        route_retrieve,
        {"analyze": "analyze", "insufficient": "insufficient"},
    )
    builder.add_edge("analyze", "summarize")
    builder.add_edge("insufficient", END)
    builder.add_edge("summarize", END)
    return builder.compile()
