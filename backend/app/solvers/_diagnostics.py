from app.domain.problem import SchedulingProblem
from app.solvers._time import to_minutes


def diagnose_infeasibility(problem: SchedulingProblem) -> list[str]:
    "Return concrete reasons the problem may be infeasible."
    
    reasons: list[str] = []
    reasons.extend(_missing_capabilities(problem))
    reasons.extend(_window_too_short_for_any_op(problem))
    reasons.extend(_insufficient_capacity_per_capability(problem))
    reasons.extend(_deadline_before_min_makespan(problem))
    return reasons


def _missing_capabilities(problem: SchedulingProblem) -> list[str]:
    "Any capability required by any product that no resource provides."
    provided = {cap for r in problem.resources for cap in r.capabilities}
    reasons: list[str] = []
    for product in problem.products:
        reasons.extend(
            [
                f"No resource has capability '{op.capability}' (required by {product.id} step {step_idx})"
                for step_idx, op in enumerate(product.route, start=1)
                if op.capability not in provided
            ]
        )
    return reasons


def _window_too_short_for_any_op(problem: SchedulingProblem) -> list[str]:
    "Operations longer than every eligible (resource, window) they can run on."
    horizon_start = problem.horizon.start
    reasons: list[str] = []
    for product in problem.products:
        for step_idx, op in enumerate(product.route, start=1):
            eligible = [r for r in problem.resources if op.capability in r.capabilities]
            if not eligible:
                continue  # already flagged by _missing_capabilities
            fits = False
            for r in eligible:
                for w in r.working_windows:
                    available_min = to_minutes(w.end, horizon_start) - to_minutes(w.start, horizon_start)
                    if available_min >= op.duration_minutes:
                        fits = True
                        break
                if fits:
                    break
            if not fits:
                reasons.append(
                    f"No working window long enough for {product.id} step {step_idx} ({op.duration_minutes} min on capability '{op.capability}')"
                )
    return reasons


def _insufficient_capacity_per_capability(problem: SchedulingProblem) -> list[str]:
    "Total work required for a capability exceeds total available capacity."

    horizon_start = problem.horizon.start
    horizon_end = problem.horizon.end

    demand: dict[str, int] = {}
    for product in problem.products:
        for op in product.route:
            demand[op.capability] = demand.get(op.capability, 0) + op.duration_minutes

    capacity: dict[str, int] = {}
    for resource in problem.resources:
        available = 0
        for w in resource.working_windows:
            clipped_start = max(w.start, horizon_start)
            clipped_end = min(w.end, horizon_end)
            if clipped_end > clipped_start:
                available += int((clipped_end - clipped_start).total_seconds() / 60)
        for cap in resource.capabilities:
            capacity[cap] = capacity.get(cap, 0) + available

    reasons: list[str] = []
    for cap, needed in demand.items():
        have = capacity.get(cap, 0)
        if needed > have:
            reasons.append(
                f"Insufficient '{cap}' capacity: {needed} min of work required, {have} min available across all resources within the horizon"
            )
    return reasons


def _deadline_before_min_makespan(problem: SchedulingProblem) -> list[str]:
    "A product's due date is before the sum of its own route durations."

    horizon_start = problem.horizon.start
    reasons: list[str] = []
    for product in problem.products:
        total_duration = sum(op.duration_minutes for op in product.route)
        earliest_completion_min = to_minutes(horizon_start, horizon_start) + total_duration
        due_min = to_minutes(product.due, horizon_start)
        if due_min < earliest_completion_min:
            reasons.append(
                f"{product.id} due at {product.due.isoformat()} but its route requires at least {total_duration} min of sequential processing"
            )
    return reasons