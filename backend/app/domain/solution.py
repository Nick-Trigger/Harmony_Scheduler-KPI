from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Assignment:
    "Assignment of a product to a resource at a specific time"

    product_id: str
    step_index: int  # base-1 per spec
    capability: str
    resource_id: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Solution:
    """Complete Schedule, Assignments only

    KPIs are computed separately in kpis.py from this solution.
    This is done so that the KPI logic can be tested independent
    of this solver, and so that the Solution can be re-scored
    using different objectives later.
    """

    assignments: tuple[Assignment, ...]
