"""Domain models for deterministic Kerala Building Rules compliance checking."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Jurisdiction(str, Enum):
    """Local authority governing the construction."""

    MUNICIPALITY = "municipality"  # Governed by KMBR 2019
    PANCHAYAT = "panchayat"  # Governed by KPBR 2019


class OccupancyGroup(str, Enum):
    """Kerala Building Rules Chapter IV Occupancy Classifications."""

    A1_RESIDENTIAL = "A1"  # Single/multi-family private residential
    A2_SPECIAL_RESIDENTIAL = "A2"  # Hostels, boarding houses, dormitories
    B_EDUCATIONAL = "B"  # Schools, colleges, training institutes
    C_MEDICAL = "C"  # Hospitals, nursing homes, dispensaries
    D_ASSEMBLY = "D"  # Theatres, auditoriums, marriage halls, places of worship
    E_OFFICE = "E"  # Government/commercial offices, professional offices
    F_MERCANTILE = "F"  # Shops, stores, shopping malls, markets
    G1_INDUSTRIAL_NON_HAZARDOUS = "G1"  # Light industry, non-hazardous factories
    G2_INDUSTRIAL_HAZARDOUS = "G2"  # Hazardous industries, chemical storage
    H_STORAGE = "H"  # Warehouses, godowns, freight depots
    I_HAZARDOUS = "I"  # Highly flammable / explosive operations
    J_MULTIPLEX = "J"  # Multiplex complexes


class PlanFacts(BaseModel):
    """Normalized measurable parameters extracted from an architectural plan."""

    jurisdiction: Jurisdiction = Field(
        default=Jurisdiction.PANCHAYAT,
        description="Local authority jurisdiction (KPBR for Panchayat, KMBR for Municipality)",
    )
    occupancy: OccupancyGroup = Field(
        default=OccupancyGroup.A1_RESIDENTIAL,
        description="Statutory occupancy classification under Chapter IV",
    )
    plot_area_sqm: float = Field(
        ...,
        gt=0,
        description="Total legal plot area in square metres (1 cent = ~40.47 m²)",
    )
    built_up_area_sqm: float = Field(
        ...,
        gt=0,
        description="Total built-up area across all floors in square metres",
    )
    ground_coverage_sqm: float = Field(
        ...,
        gt=0,
        description="Plinth area / ground footprint in square metres",
    )
    building_height_m: float = Field(
        ...,
        gt=0,
        description="Total vertical height in metres from ground to terrace floor",
    )
    number_of_floors: int = Field(
        default=1,
        ge=1,
        description="Total number of floors including ground floor",
    )
    road_width_m: float = Field(
        ...,
        gt=0,
        description="Abutting access road width in metres",
    )
    front_setback_m: float = Field(
        ...,
        ge=0,
        description="Minimum clear distance from front plot boundary to building line in metres",
    )
    rear_setback_m: float = Field(
        ...,
        ge=0,
        description="Minimum clear distance from rear plot boundary to building line in metres",
    )
    side_setback_1_m: float = Field(
        ...,
        ge=0,
        description="Side yard 1 setback in metres",
    )
    side_setback_2_m: float = Field(
        ...,
        ge=0,
        description="Side yard 2 setback in metres",
    )
    parking_slots_provided: int = Field(
        default=0,
        ge=0,
        description="Number of car parking spaces provided on site",
    )
    # Metadata for PDF traceability
    source_pdf_page: Optional[int] = Field(
        default=None,
        description="Page number in original PDF drawing where parameters were located",
    )
    bounding_boxes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Bounding box coordinates on the drawing page for redline overlays",
    )


class RuleViolation(BaseModel):
    """A mathematically or legally verified statutory infraction."""

    rule_reference: str = Field(
        ..., description="Statutory rule citation, e.g. 'Rule 25(1) / Table 6'"
    )
    parameter: str = Field(..., description="Building parameter in violation")
    severity: str = Field(
        ..., description="'high' (critical safety/setback), 'medium', or 'low'"
    )
    actual_value: float = Field(..., description="Actual value provided in the plan")
    required_value: float = Field(..., description="Statutory required threshold")
    unit: str = Field(..., description="Measurement unit (m, %, ratio, slots)")
    deficit: float = Field(
        ...,
        description="Amount by which plan falls short or exceeds the permissible limit",
    )
    description: str = Field(
        ..., description="Human-readable explanation for engineers"
    )
    statutory_clause: str = Field(
        ..., description="Exact clause / table description from KMBR/KPBR 2019"
    )
    concession_applied: Optional[str] = Field(
        default=None,
        description="Name of concession or relaxation evaluated (e.g. 'Chapter VI Small Plot')",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Page number in the submitted PDF where violation occurs",
    )


class ComplianceEvaluation(BaseModel):
    """Complete deterministic compliance evaluation result."""

    is_compliant: bool
    summary_verdict: str
    violations: List[RuleViolation]
    coverage_percent: float
    max_coverage_percent: float
    fsi_actual: float
    base_fsi: float
    max_fsi_permitted: float
    parking_required: int
    parking_slots_provided: int
    concessions_eligible: List[str]
    applied_concessions: List[str]
    rule_citations: List[str]
