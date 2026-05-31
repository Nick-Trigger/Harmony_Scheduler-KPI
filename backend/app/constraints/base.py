from typing import Protocol

from ortools.sat.python import cp_model

from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution
from app.solvers._op_vars import OpVars


class InvariantError(Exception):
    """Raised when a Solution violates a hard constraint.

    Distinct from InfeasibleError: this means the solver produced an
    invalid output (a bug), not that no solution exists.
    """

    def __init__(self, message: str):
        super().__init__(message)


class Constraint(Protocol):
    """A hard constraint with model-enforcement and post-solve validation."""

    name: str

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        ...

    def validate(self, solution: Solution, problem: SchedulingProblem) -> None:
        ...


_REGISTRY: list[Constraint] = []


def register(constraint: Constraint) -> None:
    if any(c.name == constraint.name for c in _REGISTRY):
        raise ValueError(f"constraint {constraint.name!r} is already registered")
    _REGISTRY.append(constraint)


def all_constraints() -> list[Constraint]:
    return list(_REGISTRY)