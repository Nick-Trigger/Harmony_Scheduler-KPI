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
    "Complete Schedule"

    assignments: tuple[Assignment, ...]
