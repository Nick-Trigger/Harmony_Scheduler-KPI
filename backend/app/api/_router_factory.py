from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.adapters.base import Adapter
from app.kpis import compute_kpis
from app.solvers.cpsat import solve
from app.validation import validate


class RouterFactory:
    """Registers a scheduling endpoint on the given router using the given Pydantic request model and adapter for input/output translation."""

    def __init__(
        self,
        router: APIRouter,
        request_model: type[BaseModel],
        adapter: Adapter,
        endpoint: str,
    ) -> None:
        self.router = router
        self.request_model = request_model
        self.adapter = adapter
        self.endpoint = endpoint

    def create_schedule(self) -> None:
        # Capture into locals so the inner function doesn't depend on `self`.
        request_model = self.request_model
        adapter = self.adapter

        @self.router.post(self.endpoint)
        def _create_schedule(request: request_model) -> dict[str, Any]:  # type: ignore[valid-type]
            """Compute a production schedule and return the solution + KPIs."""
            problem = adapter.parse_request(request.model_dump(by_alias=True))
            solution = solve(problem)
            validate(problem, solution)
            kpis = compute_kpis(problem, solution)
            return adapter.format_response(solution, kpis=kpis)