from ortools.sat.python import cp_model

from app.constraints.base import register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution
from app.solvers._op_vars import OpVars
from app.constraints.base import InvariantError


class CalendarConstraint:
    """Each operation must fit fully within a single working window of its resource.

    Enforcement of this constraint is split between two places:
    - `solvers/cpsat.py` creates one optional interval per (op, resource, window)
      with start/end domain constraints scoped to that window. The `OpVars`
      this constraint receives already encode the per-window structure.
    - This module's validate() re-checks each assignment lands inside one
      working window of its assigned resource.

    The model-side enforcement is intrinsic to how OpVars are constructed,
    so add_to_model is a no-op here. We keep the constraint registered for
    the validation pass and for documentation purposes.
    """

    name = "calendar"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        # Enforcement is built into _build_op_vars in cpsat.py — each optional
        # interval's start/end are constrained to its specific working window
        # via only_enforce_if(present). No additional model code needed here.
        return

    def validate(self, solution: Solution, problem: SchedulingProblem) -> None:
        resources_by_id = {r.id: r for r in problem.resources}
        for a in solution.assignments:
            resource = resources_by_id.get(a.resource_id)
            if resource is None:
                raise InvariantError(
                    f"assignment for {a.product_id} step {a.step_index} "
                    f"references unknown resource {a.resource_id!r}"
                )
            if not any(
                w.start <= a.start and a.end <= w.end for w in resource.working_windows
            ):
                raise InvariantError(
                    f"calendar violation: {a.product_id} step {a.step_index} on "
                    f"{a.resource_id} ({a.start.isoformat()}–{a.end.isoformat()}) "
                    f"does not fit inside any working window"
                )


register(CalendarConstraint())
