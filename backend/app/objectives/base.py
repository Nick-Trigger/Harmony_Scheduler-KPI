from typing import Protocol

from ortools.sat.python import cp_model

from app.domain.problem import SchedulingProblem
from app.solvers._op_vars import OpVars


class ObjectiveFn(Protocol):
    "Function signaure for adding an objective to the model. Registered at app.objectives.base.register at runtime."
    
    def __call__(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None: ...

# Registry of objective functions. Each objective function must be registered here to be used by the solver.
_REGISTRY: dict[str, ObjectiveFn] = {}


def register(name:str, fn: ObjectiveFn) -> None:
    "Register an objective function to be used by the solver via settings.objective_mode."
    if name in _REGISTRY:
        raise ValueError(f"Objective function '{name!r}' is already registered.")
    _REGISTRY[name] = fn
    
def get(name: str) -> ObjectiveFn:
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY)) or "(none registered)"
        raise ValueError(
            f"unknown objective_mode {name!r}; available: {available}"
        ) from None
    
def available() -> list[str]:
    "Return a list of registered objective function names."
    return sorted(_REGISTRY)