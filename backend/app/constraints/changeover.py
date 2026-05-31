from datetime import timedelta

from ortools.sat.python import cp_model

from app.constraints.base import register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Assignment, Solution
from app.solvers.helpers import resource_presence
from app.solvers._op_vars import OpVars
from app.constraints.base import InvariantError

class ChangeoverConstraint:
    """When consecutive ops on the same resource belong to different families,
    insert the required setup time before the later op.

    Uses the disjunctive pattern: one boolean per unordered op pair per shared
    resource selects the ordering, and the setup constraint for the chosen
    direction is enforced conditionally.
    """

    name = "changeover"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        matrix = problem.changeover_matrix
        n = len(op_vars)

        for i in range(n):
            for j in range(i + 1, n):
                op_i = op_vars[i]
                op_j = op_vars[j]

                # Different ops within the same product's route can't share a
                # resource in practice (different capabilities, precedence
                # enforced elsewhere), so skip the pair entirely.
                if op_i.product_id == op_j.product_id:
                    continue

                shared_resources = {
                    r_id for (r_id, _) in op_i.presences
                } & {
                    r_id for (r_id, _) in op_j.presences
                }
                if not shared_resources:
                    continue

                setup_ij = matrix.setup_minutes(op_i.family, op_j.family)
                setup_ji = matrix.setup_minutes(op_j.family, op_i.family)
                # Same-family transitions have zero setup → no-overlap already
                # covers them, no constraint needed.
                if setup_ij == 0 and setup_ji == 0:
                    continue

                for r_id in shared_resources:
                    i_on_r = resource_presence(model, op_i, r_id)
                    j_on_r = resource_presence(model, op_j, r_id)

                    # Single boolean per unordered pair selects the order on r.
                    # The unselected branch is enforced via `.Not()` — together
                    # the constraints force the boolean to reflect the actual
                    # ordering whenever both ops are on this resource.
                    i_before_j = model.new_bool_var(
                        f"co_{op_i.product_id}s{op_i.step_index}_before_"
                        f"{op_j.product_id}s{op_j.step_index}_on_{r_id}"
                    )

                    if setup_ij > 0:
                        model.add(
                            op_j.start >= op_i.end + setup_ij
                        ).only_enforce_if([i_on_r, j_on_r, i_before_j])

                    if setup_ji > 0:
                        model.add(
                            op_i.start >= op_j.end + setup_ji
                        ).only_enforce_if([i_on_r, j_on_r, i_before_j.Not()])

    def validate(self, solution: Solution, problem: SchedulingProblem) -> None:
        family_by_product = {p.id: p.family for p in problem.products}
        matrix = problem.changeover_matrix

        by_resource: dict[str, list[Assignment]] = {}
        for a in solution.assignments:
            by_resource.setdefault(a.resource_id, []).append(a)

        for resource_id, assignments in by_resource.items():
            assignments.sort(key=lambda a: a.start)
            for prev, curr in zip(assignments, assignments[1:]):
                setup = matrix.setup_minutes(
                    family_by_product[prev.product_id],
                    family_by_product[curr.product_id],
                )
                if setup == 0:
                    continue
                actual_gap = curr.start - prev.end
                required = timedelta(minutes=setup)
                if actual_gap < required:
                    raise InvariantError(
                        f"changeover violation on {resource_id}: "
                        f"{prev.product_id}->{curr.product_id} needs {setup} "
                        f"min setup but only {int(actual_gap.total_seconds() / 60)} "
                        f"min between {prev.end.isoformat()} and "
                        f"{curr.start.isoformat()}"
                    )


register(ChangeoverConstraint())