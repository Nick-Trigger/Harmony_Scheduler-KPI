from typing import Any, Protocol

from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution


class Adapter(Protocol):
    """
    Translation layer between client JSON shape and canonical domain model

    This is the only place where clinet-specific logic should be implemented.
    """

    def parse_request(self, payload: dict[str, Any]) -> SchedulingProblem:
        "Parse the client request payload into a canonical SchedulingProblem"
        ...

    def format_response(
        self,
        solution: Solution,
        kpis: dict[str, Any],
    ) -> dict[str, Any]:
        "Format the canonical Solution and KPIs into a client-specific response shape"
        ...
