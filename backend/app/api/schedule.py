from typing import Any

from fastapi import APIRouter

from app.adapters.client_a import ClientARequest, format_response, parse_request
from app.kpis import compute_kpis
from app.solvers.cpsat import solve
from app.validation import validate

router = APIRouter()


@router.post("/schedule")
def create_schedule(request: ClientARequest) -> dict[str, Any]:
    "Compute a production schedule for a given scheduling problem and return the solution along with KPIs."
    problem = parse_request(request.model_dump(by_alias=True))
    solution = solve(problem)
    kpis = compute_kpis(problem, solution)
    validate(problem, solution)
    return format_response(solution, kpis=kpis)
