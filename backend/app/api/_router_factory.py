from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.adapters.base import Adapter
from app.kpis import compute_kpis
from app.solvers.cpsat import solve
from app.validation import validate


@dataclass(frozen=True)
class ClientConfig:
    request_model: type[BaseModel]
    adapter: Adapter
    endpoint: str


def register_client(router: APIRouter, config: ClientConfig) -> None:
    # Capture into locals so the inner function closes over them, not `config`.
    request_model = config.request_model
    adapter = config.adapter

    @router.post(config.endpoint)
    def _create_schedule(request: request_model) -> dict[str, Any]:  # type: ignore[valid-type]
        """Compute a production schedule and return the solution + KPIs."""
        problem = adapter.parse_request(request.model_dump(by_alias=True))
        solution = solve(problem)
        validate(problem, solution)
        kpis = compute_kpis(problem, solution)
        return adapter.format_response(solution, kpis=kpis)
