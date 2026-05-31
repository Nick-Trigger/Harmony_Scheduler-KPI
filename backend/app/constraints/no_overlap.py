from ortools.sat.python import cp_model

from app.constraints.base import register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Assignment, Solution
from app.solvers._op_vars import OpVars
from app.constraints.base import InvariantError


class NoOverlapConstraint:
    """Each resource can run at most one operation at a time."""

    name = "no_overlap"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        # Collect all intervals for each resource across every (resource, window)
        # presence. Only the chosen one will be present, but no-overlap is
        # written across all of them — optional intervals only count when present.
        intervals_per_resource: dict[str, list[cp_model.IntervalVar]] = {
            r.id: [] for r in problem.resources
        }
        for ov in op_vars:
            for (r_id, _w_idx), interval in ov.intervals.items():
                intervals_per_resource[r_id].append(interval)

        for intervals in intervals_per_resource.values():
            if intervals:
                model.add_no_overlap(intervals)

    def validate(self, solution: Solution, problem: SchedulingProblem) -> None:
        by_resource: dict[str, list[Assignment]] = {}
        for a in solution.assignments:
            by_resource.setdefault(a.resource_id, []).append(a)

        for resource_id, assignments in by_resource.items():
            assignments.sort(key=lambda a: a.start)
            for prev, curr in zip(assignments, assignments[1:]):
                if curr.start < prev.end:
                    raise InvariantError(
                        f"overlap on {resource_id}: {prev.product_id} step "
                        f"{prev.step_index} ({prev.start.isoformat()}–"
                        f"{prev.end.isoformat()}) overlaps {curr.product_id} "
                        f"step {curr.step_index} ({curr.start.isoformat()}–"
                        f"{curr.end.isoformat()})"
                    )


register(NoOverlapConstraint())