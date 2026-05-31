from ortools.sat.python import cp_model

from app.constraints.base import register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution
from app.solvers._op_vars import OpVars
from app.constraints.base import InvariantError


class DurationConstraint:
    """Each assignment's duration matches the route operation's specified duration.

    Model-side: enforced when OpVars are constructed in cpsat.py via
    `model.add(end == start + duration)`. The post-solve check is a
    consistency guard against any bookkeeping bug downstream of the solver.
    """

    name = "duration"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        # end == start + duration is added inside _build_op_vars in cpsat.py.
        return

    def validate(self, solution: Solution, problem: SchedulingProblem) -> None:
        products_by_id = {p.id: p for p in problem.products}
        for a in solution.assignments:
            product = products_by_id.get(a.product_id)
            if product is None:
                raise InvariantError(
                    f"assignment references unknown product {a.product_id!r}"
                )
            step_idx_zero = a.step_index - 1
            if not (0 <= step_idx_zero < len(product.route)):
                raise InvariantError(
                    f"step_index {a.step_index} out of range for {a.product_id} "
                    f"(route has {len(product.route)} steps)"
                )
            expected = product.route[step_idx_zero].duration_minutes
            actual = int((a.end - a.start).total_seconds() / 60)
            if actual != expected:
                raise InvariantError(
                    f"duration mismatch for {a.product_id} step {a.step_index}: "
                    f"route says {expected} min, assignment has {actual} min"
                )


register(DurationConstraint())