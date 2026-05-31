from ortools.sat.python import cp_model

from app.constraints.base import register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution
from app.solvers._op_vars import OpVars
from app.constraints.base import InvariantError


class HorizonConstraint:
    """All scheduled times must lie within the planning horizon.

    The CP-SAT model enforces this via integer variable domains — start and
    end variables for each operation are bounded at [0, horizon_end_min]
    when constructed. The model-side enforcement is intrinsic to how OpVars
    are built, so add_to_model is a no-op here. Validation re-checks the
    bound from the final assignment timestamps.
    """

    name = "horizon"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        # Domain bounds applied to op_vars.start/end at construction time.
        return

    def validate(self, solution: Solution, problem: SchedulingProblem) -> None:
        horizon_start = problem.horizon.start
        horizon_end = problem.horizon.end
        for a in solution.assignments:
            if a.start < horizon_start or a.end > horizon_end:
                raise InvariantError(
                    f"horizon violation: {a.product_id} step {a.step_index} "
                    f"({a.start.isoformat()}–{a.end.isoformat()}) is outside "
                    f"the horizon ({horizon_start.isoformat()}–"
                    f"{horizon_end.isoformat()})"
                )


register(HorizonConstraint())