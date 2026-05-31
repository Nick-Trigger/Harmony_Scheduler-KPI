from ortools.sat.python import cp_model

from app.constraints.base import register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution
from app.solvers._op_vars import OpVars
from app.constraints.base import InvariantError


class PrecedenceConstraint:
    "Step n+1 of a product's route cannot start before step n ends."

    name = "precedence"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        
        by_product: dict[str, list[OpVars]] = {}
        for ov in op_vars:
            by_product.setdefault(ov.product_id, []).append(ov)

        constraints_added = 0
        for _, steps in by_product.items():
            steps.sort(key=lambda ov: ov.step_index)
            for prev, curr in zip(steps, steps[1:]):
                model.add(curr.start >= prev.end)
                constraints_added += 1

    def validate(self, solution: Solution, problem: SchedulingProblem) -> None:
        by_product: dict[str, list] = {}
        for a in solution.assignments:
            by_product.setdefault(a.product_id, []).append(a)

        for product_id, assignments in by_product.items():
            assignments.sort(key=lambda a: a.step_index)
            for prev, curr in zip(assignments, assignments[1:]):
                if curr.start < prev.end:
                    raise InvariantError(
                        f"precedence violation in {product_id}: step "
                        f"{curr.step_index} starts before step {prev.step_index} ends"
                    )


register(PrecedenceConstraint())
