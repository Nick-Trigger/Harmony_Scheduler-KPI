from typing import Protocol

from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution


class InfeasibleError(Exception):
    """Raised when no feasible schedule exists.

    `reasons` is a list of explanations from the solver
    (or by upstream validation) and surfaced in the API's error response
    """

    def __init__(self, reasons: list[str]):
        super().__init__("infeasible")
        self.reasons = reasons


class Solver(Protocol):
    def solve(self, problem: SchedulingProblem) -> Solution: ...