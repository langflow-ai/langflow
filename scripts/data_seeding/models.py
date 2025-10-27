"""Data models for agent seeding."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class AgentDomain(str, Enum):
    """Domain areas for agents."""
    ACTUARIAL_FINANCE = "Actuarial / Finance"
    APPEALS_GRIEVANCES = "Appeals & Grievances"
    CARE_MANAGEMENT = "Care Management"
    CLAIMS_OPERATIONS = "Claims Operations"
    CLINICAL_RESEARCH = "Clinical Research"
    COMPLIANCE_AUDIT = "Compliance / Audit"
    CONTRACTING_RFP = "Contracting & RFP"
    HEDIS_CARE_GAP = "HEDIS Care Gap"
    MEMBER_ENGAGEMENT = "Member Engagement"
    NETWORK_MANAGEMENT = "Network Management"
    PATIENT_EXPERIENCE = "Patient Experience"
    PBM_PHARMACY = "PBM / Pharmacy"
    POPULATION_HEALTH = "Population Health"
    PROVIDER_DATA_MANAGEMENT = "Provider Data Management"
    PROVIDER_ENABLEMENT = "Provider Enablement"
    PROVIDER_OPS_CONTRACTING = "Provider Ops / Contracting"
    QUALITY_STARS = "Quality / Stars"
    REVENUE_CYCLE_MANAGEMENT = "Revenue Cycle Management"
    RISK_ADJUSTMENT = "Risk Adjustment"
    UTILIZATION_MANAGEMENT = "Utilization Management"
    UTILIZATION_MANAGEMENT_SPACE = "Utilization Management "  # Note: there's a trailing space in the data
    UTILIZATION_MANAGEMENT_MULTI_1 = "Utilization Management/ Care gap/ Care Management / Claims/ Chart Review"
    UTILIZATION_MANAGEMENT_MULTI_2 = "Utilization Management/ Care gap/ Care Management/ Claims"
    UTILIZATION_MANAGEMENT_MULTI_3 = "Utilization Management/ Care gap/ Care Management/ Claims Operations"


@dataclass
class AgentData:
    """Parsed agent data from TSV file."""
    domain_area: str
    agent_name: str
    description: str
    applicable_to_payers: bool
    applicable_to_payviders: bool
    applicable_to_providers: bool
    connectors: str
    goals: str
    kpis: str
    tools: str

    @property
    def endpoint_name(self) -> str:
        """Generate a valid endpoint name from agent name."""
        # Convert to lowercase, replace spaces with hyphens, remove special chars
        name = self.agent_name.lower()
        name = name.replace(" ", "-")
        name = "".join(c for c in name if c.isalnum() or c in ["-", "_"])
        return name[:50]  # Limit length

    @property
    def tags(self) -> list[str]:
        """Generate tags from domain area only."""
        # Split by "/" delimiter to handle multi-domain areas
        tags = []
        for part in self.domain_area.split("/"):
            # Strip whitespace and filter out empty strings
            clean_tag = part.strip()
            if clean_tag:  # Only add non-empty tags
                tags.append(clean_tag)

        # If no "/" delimiter found, return the original domain as a single tag
        return tags if tags else [self.domain_area.strip()]

    @property
    def category(self) -> str:
        """Category for published flow."""
        return self.domain_area


@dataclass
class SeedingResult:
    """Result of seeding operation."""
    flow_id: Optional[UUID] = None
    published_flow_id: Optional[UUID] = None
    agent_name: str = ""
    success: bool = False
    error_message: Optional[str] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class BatchResult:
    """Result of batch seeding operation."""
    total_processed: int
    successful: int
    failed: int
    results: list[SeedingResult]
    start_time: datetime
    end_time: datetime

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_processed == 0:
            return 0.0
        return self.successful / self.total_processed

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class ValidationError:
    """Validation error details."""
    field: str
    value: str
    error: str