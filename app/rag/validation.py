"""Validation for building plan inputs.

Verifies that submitted plan text or uploaded documents contain recognizable
architectural, zoning, and physical parameters before compliance processing.
"""

from __future__ import annotations

import re

_BUILDING_ENTITIES = (
    "building",
    "buildings",
    "structure",
    "structures",
    "house",
    "houses",
    "villa",
    "villas",
    "apartment",
    "apartments",
    "flat",
    "flats",
    "residence",
    "residential",
    "commercial",
    "office",
    "hospital",
    "clinic",
    "dispensary",
    "school",
    "college",
    "institution",
    "institutional",
    "mall",
    "complex",
    "multiplex",
    "warehouse",
    "factory",
    "industrial",
    "educational",
    "hazardous",
    "mercantile",
    "assembly",
    "occupancy",
    "dwelling",
    "shed",
    "godown",
    "cottage",
    "auditorium",
    "lodge",
    "hostel",
    "hotel",
    "kbr",
    "kpmbr",
    "kerala building",
    "lsgd",
    "panchayat",
    "municipality",
    "corporation",
    "group a",
    "group a1",
    "group a2",
    "group b",
    "group c",
    "group d",
    "group e",
    "group f",
    "group g",
    "group h",
    "group i",
    "group j",
    "development",
    "construction",
    "blueprint",
    "floor plan",
    "site plan",
    "layout plan",
    "architectural",
    "drawing",
)

_PLANNING_PARAMETERS = (
    "floor",
    "floors",
    "storey",
    "storeys",
    "story",
    "stories",
    "level",
    "levels",
    "height",
    "tall",
    "depth",
    "width",
    "length",
    "dimension",
    "dimensions",
    "meter",
    "meters",
    "metre",
    "metres",
    "centimeter",
    "centimeters",
    "centimetre",
    "centimetres",
    "sqm",
    "sq.m",
    "sq m",
    "sq.metre",
    "sq.metres",
    "sq.meter",
    "sq.meters",
    "square metre",
    "square metres",
    "square meter",
    "square meters",
    "sq ft",
    "sqft",
    "square feet",
    "cent",
    "cents",
    "plot",
    "site",
    "area",
    "built-up",
    "builtup",
    "built up",
    "plinth",
    "carpet area",
    "fsi",
    "far",
    "floor space index",
    "floor area ratio",
    "coverage",
    "ground coverage",
    "setback",
    "setbacks",
    "set-back",
    "set-backs",
    "front setback",
    "rear setback",
    "side setback",
    "front distance",
    "rear distance",
    "side distance",
    "front open space",
    "rear open space",
    "side open space",
    "open space",
    "open spaces",
    "road width",
    "street width",
    "access width",
    "road",
    "street",
    "boundary",
    "boundaries",
    "abutting",
    "parking",
    "car parking",
    "staircase",
    "stairs",
    "fire escape",
    "fire safety",
    "exit",
    "corridor",
    "passage",
    "balcony",
    "verandah",
    "veranda",
    "terrace",
    "mezzanine",
    "basement",
    "cantilever",
    "projection",
    "canopy",
    "parapet",
    "ground floor",
    "first floor",
    "second floor",
    "living room",
    "bedroom",
    "kitchen",
)


_ENTITIES_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(t) for t in sorted(_BUILDING_ENTITIES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
_PARAMS_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(
        re.escape(t) for t in sorted(_PLANNING_PARAMETERS, key=len, reverse=True)
    )
    + r")\b",
    re.IGNORECASE,
)


def is_building_plan_text(text: str) -> bool:
    """Check if the given text represents a building plan or architectural specification.

    Requires:
    1. A minimum non-whitespace length of 15 characters.
    2. At least one architectural entity AND at least one planning/dimensional parameter,
       OR at least two distinct planning/dimensional parameters.
    """
    if not text or not isinstance(text, str):
        return False

    cleaned = text.strip()
    if len(cleaned) < 15:
        return False

    # Regex word-boundary checks prevent false-positive substring hits
    entity_hits = len(set(_ENTITIES_PATTERN.findall(cleaned)))
    param_hits = len(set(_PARAMS_PATTERN.findall(cleaned)))

    if (entity_hits >= 1 and param_hits >= 1) or param_hits >= 2:
        return True

    return False


def validate_building_plan_text(text: str) -> None:
    """Validate that text content is an architectural building plan.

    Raises:
        ValueError: with detail message if the content is not a building plan.
    """
    if not is_building_plan_text(text):
        raise ValueError("The content of the file is not a building plan.")
