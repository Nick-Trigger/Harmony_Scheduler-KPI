import math as m

from typing import Any

from app.domain.problem import SchedulingProblem
from app.domain.solution import Assignment, Solution


# %% Tardiness
def _compute_tardiness(problem: SchedulingProblem, solution: Solution) -> int:
    """Sum over products of max(0, last_op_end - due) in minutes."""
    # Find each product's last assignment by step_index.
    last_by_product: dict[str, Assignment] = {}
    for a in solution.assignments:
        prev = last_by_product.get(a.product_id)
        if prev is None or a.step_index > prev.step_index:
            last_by_product[a.product_id] = a

    total = 0
    for product in problem.products:
        last = last_by_product.get(product.id)
        if last is None:
            continue  # Product had no assignments; shouldn't happen but guard anyway.
        late = (last.end - product.due).total_seconds() / 60
        total += max(0, int(m.floor(late)))  # round down bc this is expeced to be -
    return total


# %% Changeovers


def _compute_changeovers(
    problem: SchedulingProblem, solution: Solution, family_by_product: dict[str, str]
) -> tuple[int, int]:
    """Count changeovers and sum their durations in minutes."""
    matrix = problem.changeover_matrix

    # Group assignments by resource.
    by_resource: dict[str, list[Assignment]] = {}
    for a in solution.assignments:
        by_resource.setdefault(a.resource_id, []).append(a)

    count = 0
    minutes = 0
    for assignments in by_resource.values():
        assignments.sort(key=lambda a: a.start)
        for prev, curr in zip(assignments, assignments[1:]):
            prev_family = family_by_product[prev.product_id]
            curr_family = family_by_product[curr.product_id]
            if prev_family != curr_family:
                count += 1
                minutes += matrix.setup_minutes(prev_family, curr_family)
    return count, minutes


# %% Makespan
def _compute_makespan(solution: Solution) -> int:
    """Latest assignment end minus earliest assignment start, in minutes."""
    if not solution.assignments:
        return 0
    earliest_start = min(a.start for a in solution.assignments)
    latest_end = max(a.end for a in solution.assignments)
    return int((latest_end - earliest_start).total_seconds() / 60)


# %% Utilization
def _compute_utilization(
    problem: SchedulingProblem, solution: Solution
) -> dict[str, int]:
    """Per resource: processing minutes / available calendar minutes * 100.

    Changeover minutes are excluded from the numerator (spec footnote).
    Available minutes are the resource's calendar windows (ie: working_windows) clipped to the horizon.
    """
    horizon_start = problem.horizon.start
    horizon_end = problem.horizon.end

    # Numerator: sum of processing minutes per resource.
    processing_by_resource: dict[str, int] = {r.id: 0 for r in problem.resources}
    for a in solution.assignments:
        minutes = int((a.end - a.start).total_seconds() / 60)
        processing_by_resource[a.resource_id] += minutes

    # Denominator: sum of available minutes per resource, clipped to horizon.
    utilization: dict[str, int] = {}
    for resource in problem.resources:
        available = 0
        for window in resource.working_windows:
            clipped_start = max(window.start, horizon_start)
            clipped_end = min(window.end, horizon_end)
            if clipped_end > clipped_start:
                available += int((clipped_end - clipped_start).total_seconds() / 60)

        if available == 0:
            utilization[resource.id] = 0
            continue

        pct = processing_by_resource[resource.id] / available * 100
        utilization[resource.id] = round(pct)

    return utilization


# %% Finally, KPIs
def compute_kpis(problem: SchedulingProblem, solution: Solution) -> dict[str, Any]:
    "Compute KPIs for a given scheduling problem and its solution."

    family_by_product = {p.id: p.family for p in problem.products}

    changeover_count, changeover_minutes = _compute_changeovers(
        problem, solution, family_by_product
    )

    return {
        "tardiness_minutes": _compute_tardiness(problem, solution),
        "changeover_count": changeover_count,
        "changeover_minutes": changeover_minutes,
        "makespan_minutes": _compute_makespan(solution),
        "utilization_pct": _compute_utilization(problem, solution),
    }
