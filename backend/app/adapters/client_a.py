from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.problem import (
    ChangeoverMatrix,
    Horizon,
    Operation,
    Product,
    Resource,
    SchedulingProblem,
    SolverSettings,
    WorkingWindow,
)

from app.domain.solution import Solution

# %% Client A Adapter
"""
This adapter translates between the client A JSON shape and the canonical domain model.
"""

class _HorizonIn(BaseModel):
    start: datetime
    end: datetime
    
class _ResourceIn(BaseModel):
    id: str
    capabilities: list[str]
    calendar: list[list[datetime]]

class _OperationIn(BaseModel):
    capability: str
    duration_minutes: int
    
class _ProductIn(BaseModel):
    id: str
    family: str
    due: datetime
    route: list[_OperationIn]
    
class _ChangeoverMatrixIn(BaseModel):
    values: dict[str, int] = Field(
        ...,
        description="Changeover times in minutes between families, e.g. 'standard->premium': 20"
    )
    
class _SettingsIn(BaseModel):
    time_limit_seconds: int
    objective_mode: str
    

class ClientARequest(BaseModel):
    horizon: _HorizonIn
    resources: list[_ResourceIn]
    products: list[_ProductIn]
    changeover_matrix: _ChangeoverMatrixIn = Field(..., alias="changeover_matrix_minutes")
    settings: _SettingsIn
    
    model_config = {
        "populate_by_name": True,
    }
    
# %% Parse Json to SchedulingProblem

def parse_request(payload: dict[str, Any]) -> SchedulingProblem:
    "Translate the client A request payload into a canonical SchedulingProblem"
    request = ClientARequest.model_validate(payload)
    
    horizon = Horizon(
        start=request.horizon.start,
        end=request.horizon.end,
    )
    
    resources = tuple(
        Resource(
            id=r.id,
            capabilities=frozenset(r.capabilities),
            working_windows=tuple(
                WorkingWindow(start=window[0], end=window[1]) for window in r.calendar
            )
        )
        for r in request.resources
    )
    
    products = tuple(
        Product(
            id=p.id,
            family=p.family,
            due=p.due,
            route=tuple(
                Operation(capability=op.capability, duration_minutes=op.duration_minutes)
                for op in p.route
            )
        )
        for p in request.products
    )
    
    def _parse_changeover_key(key: str) -> tuple[str, str]:
        "Split a changeover key. eg: 'standard->premium' -> ('standard', 'premium')"
        parts = key.split("->")
        if len(parts) != 2:
            raise ValueError(f"Invalid changeover key: {key}, expected format 'from_family->to_family'")
        return parts[0], parts[1]
    
    changeover_matrix = ChangeoverMatrix(
        values={
            _parse_changeover_key(k): v for k, v in request.changeover_matrix.values.items()
        }
    )
    
    settings = SolverSettings(
        time_limit_seconds=request.settings.time_limit_seconds,
        objective_mode=request.settings.objective_mode,
    )
    
    return SchedulingProblem(
        horizon=horizon,
        resources=resources,
        products=products,
        changeover_matrix=changeover_matrix,
        settings=settings,
    )
    
# %% Format Solution: SchedulingSolution and KPIs to Json

def format_response(solution: Solution, kpis: dict[str, Any]) -> dict[str, Any]:
    "Translate the canonical Solution and KPIs into a client A's response shape"
    return {
        "assignments": [
            {
                "product_id": a.product_id,
                "step_index": a.step_index,
                "capability": a.capability,
                "resource_id": a.resource_id,
                "start": a.start.isoformat(),
                "end": a.end.isoformat(),
            }
            for a in solution.assignments
        ],
        "kpis": kpis,
    }