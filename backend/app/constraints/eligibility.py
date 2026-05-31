from ortools.sat.python import cp_model

from app.constraints.base import register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution
from app.solvers._op_vars import OpVars
from app.constraints.base import InvariantError


class EligibilityConstraint:
    """Each operation runs on a resource that has the required capability.

    Model-side enforcement is intrinsic: when OpVars are constructed in
    cpsat.py, presence booleans are only created for resources whose
    capabilities include the operation's required capability. There is no
    presence variable connecting an op to an ineligible resource, so the
    solver cannot place it there.

    The validate pass re-checks each assignment against problem.resources
    as defense in depth.
    """

    name = "eligibility"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        # Eligibility is filtered into the OpVars at construction time.
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
            if a.capability not in resource.capabilities:
                raise InvariantError(
                    f"resource {a.resource_id} lacks required capability "
                    f"{a.capability!r} (used by {a.product_id} step {a.step_index})"
                )


register(EligibilityConstraint())