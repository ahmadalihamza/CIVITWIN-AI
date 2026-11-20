from hashlib import sha256
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.dataset import MAX_COST_PKR, Contract, Dataset, Identifier

DEFAULT_DATASET_ID = "demo-bajaur-v1"


def scaled_visits(visits: int, multiplier_pct: int, stress_multiplier_pct: int = 100) -> int:
    """Round nonnegative scaled weekly visits half up, using integer arithmetic."""
    return (visits * multiplier_pct * stress_multiplier_pct + 5_000) // 10_000


class PlanSpec(Contract):
    dataset_version_id: Identifier
    budget_pkr: Annotated[int, Field(ge=0, le=MAX_COST_PKR)]
    max_new_units: Annotated[int, Field(ge=0, le=50)]
    threshold_minutes: Annotated[int, Field(ge=1, le=240)]
    demand_multiplier_pct: Annotated[int, Field(ge=1, le=300)]
    equity_min_pct: Annotated[int, Field(ge=0, le=100)]
    policy: Literal["coverage_first"]
    seed: Annotated[int, Field(ge=0, le=2_147_483_647)]

    @property
    def plan_hash(self) -> str:
        from app.domain.dataset import canonical_json

        return sha256(canonical_json(self.model_dump(mode="json"))).hexdigest()

    def validate_for(self, dataset: Dataset) -> "PlanSpec":
        if self.dataset_version_id != dataset.id:
            raise ValueError("Plan dataset version does not match the loaded dataset.")
        if self.max_new_units > dataset.eligible_candidate_count:
            raise ValueError(
                f"At most {dataset.eligible_candidate_count} eligible candidates are available."
            )
        if not any(
            scaled_visits(row.demand_visits_per_week, self.demand_multiplier_pct)
            for row in dataset.communities
        ):
            raise ValueError("Planning requires positive total weekly demand after scaling.")
        return self


def default_plan(dataset_version_id: str = DEFAULT_DATASET_ID) -> PlanSpec:
    return PlanSpec(
        dataset_version_id=dataset_version_id,
        budget_pkr=300_000,
        max_new_units=2,
        threshold_minutes=45,
        demand_multiplier_pct=100,
        equity_min_pct=0,
        policy="coverage_first",
        seed=2026,
    )
