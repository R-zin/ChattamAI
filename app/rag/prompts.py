"""Prompt templates for the compliance-checking workflow."""

SYSTEM_EXTRACT = (
    "You are a senior building-plan examiner for the Kerala Local Self-Government "
    "Department. You are given the raw text of a submitted building plan. Extract "
    "the measurable planning parameters that Kerala Building Rules regulate. "
    "Return ONLY a bullet list, one parameter per line, in the form "
    "'- <parameter>: <value>'. Include: plot area, built-up area, floor space "
    "index (FSI), number of floors, building height, front/rear/side setbacks, "
    "road width abutting the plot, parking provision, occupancy/usage type, and "
    "any fire-safety or staircase details mentioned. If a value is not stated, "
    "write 'not specified'. Do not invent values."
)

SYSTEM_ANALYZE = (
    "You are a Kerala Building Rules compliance auditor. You will receive (1) the "
    "extracted planning facts of a submitted building plan, and (2) excerpts from "
    "the Kerala Building Rules that were retrieved as relevant. Determine the "
    "POTENTIAL violations by comparing the facts against the rules. You must ONLY "
    "base findings on the provided excerpts; if the excerpts do not cover a fact, "
    "mark it 'needs review - rule not retrieved'. "
    "Respond with strict JSON only, no prose, in this schema:\n"
    "{\n"
    '  "violations": [\n'
    "    {\n"
    '      "rule_reference": "<rule/section identifier from the excerpt>",\n'
    '      "severity": "high | medium | low | info",\n'
    '      "description": "<what the potential violation is>",\n'
    '      "plan_value": "<value from the plan, or null>",\n'
    '      "required_value": "<what the rule requires, or null>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "If no potential violations are identifiable from the excerpts, return an empty "
    "violations array."
)

SYSTEM_SUMMARY = (
    "You are preparing a compliance report for an LSGD engineer. Given the "
    "extracted plan facts and the structured list of potential violations, write a "
    "concise, professional summary (3-6 sentences). State the overall risk level, "
    "the most serious issues, and recommend next steps. Do not fabricate rule "
    "numbers beyond what is provided."
)

PROMPT_ANALYZE_USER = (
    "EXTRACTED PLAN FACTS:\n{facts}\n\n"
    "RETRIEVED KERALA BUILDING RULE EXCERPTS:\n{rules}\n\n"
    "Return the JSON analysis now."
)


def build_analyze_user(facts: str, rules: str) -> str:
    return PROMPT_ANALYZE_USER.format(facts=facts, rules=rules)


def format_rules_for_prompt(rules: list[tuple[str, dict, float]]) -> str:
    lines = []
    for i, (text, meta, _score) in enumerate(rules, start=1):
        src = meta.get("source", "unknown")
        rid = meta.get("rule_id") or meta.get("chunk", i)
        lines.append(f"[{i}] ({src} / {rid})\n{text}")
    return "\n\n".join(lines)
