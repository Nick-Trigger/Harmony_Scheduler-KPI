from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.domain.problem import Operation, Product, Resource, SchedulingProblem
from app.domain.solution import Assignment, Solution
from app.solvers._time import from_minutes, to_minutes
from app.solvers.base import InfeasibleError

# %% Operation Variables


@dataclass
class _OpVars:
    "CP-SAT variables for one operation in one product's route."

    product_id: str
    step_index: int  # 1-based to match wire format
    capability: str
    duration: int

    start: cp_model.IntVar  # minutes since horizon start
    end: cp_model.IntVar

    # One optional interval per eligible resource. Exactly one is present.
    presences: dict[tuple[str, int], cp_model.IntVar]
    intervals: dict[tuple[str, int], cp_model.IntervalVar]


# %% Solver Entry

def solve(problem: SchedulingProblem) -> Solution:
    horizon_start = problem.horizon.start
    horizon_end_min = to_minutes(problem.horizon.end, horizon_start)

    model = cp_model.CpModel()

    # Build operation variables and collect them per resource for no-overlap.
    op_vars: list[_OpVars] = []
    intervals_per_resource: dict[str, list[cp_model.IntervalVar]] = {
        r.id: [] for r in problem.resources
    }

    for product in problem.products:
        for step_idx_zero, operation in enumerate(product.route):
            ov = _build_op_vars(
                model=model,
                product=product,
                step_index=step_idx_zero + 1,
                operation=operation,
                resources=problem.resources,
                horizon_start=horizon_start,
                horizon_end_min=horizon_end_min,
            )
            op_vars.append(ov)
            for (resource_id, _w_idx), interval in ov.intervals.items():
                intervals_per_resource[resource_id].append(interval)

    # --- Constraint: precedence within each product's route ---
    _add_precedence_constraints(model, op_vars, problem.products)

    # --- Constraint: no overlap on each resource ---
    for resource_id, intervals in intervals_per_resource.items():
        if intervals:
            model.add_no_overlap(intervals)

    # --- Objective: minimize total tardiness ---
    _add_min_tardiness_objective(model, op_vars, problem, horizon_end_min)

    # Solve 
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(problem.settings.time_limit_seconds)
    
    # --- Determinism: fix worker count and random seed. ---
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42

    status = solver.solve(model)

    if status == cp_model.INFEASIBLE:
        raise InfeasibleError(["solver reports the model is infeasible"])
    if status == cp_model.MODEL_INVALID:
        raise InfeasibleError(["solver reports the model is invalid"])
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise InfeasibleError(
            ["solver did not find a feasible solution within the time limit"]
        )

    return _extract_solution(solver, op_vars, horizon_start)


# %% Helper Functions

def _build_op_vars(
    *,
    model: cp_model.CpModel,
    product: Product,
    step_index: int,
    operation: Operation,
    resources: tuple[Resource, ...],
    horizon_start,
    horizon_end_min: int,
) -> _OpVars:
    eligible = [r for r in resources if operation.capability in r.capabilities]
    if not eligible:
        raise InfeasibleError(
            [
                f"no resource has capability '{operation.capability}' "
                f"(required by {product.id} step {step_index})"
            ]
        )

    prefix = f"{product.id}_s{step_index}"
    start = model.new_int_var(0, horizon_end_min, f"{prefix}_start")
    end = model.new_int_var(0, horizon_end_min, f"{prefix}_end")
    model.add(end == start + operation.duration_minutes)

    presences: dict[tuple[str, int], cp_model.IntVar] = {}
    intervals: dict[tuple[str, int], cp_model.IntervalVar] = {}

    for r in eligible:
        for w_idx, window in enumerate(r.working_windows):
            win_start_min = to_minutes(window.start, horizon_start)
            win_end_min = to_minutes(window.end, horizon_start)

            # If the window can't even hold the operation, skip: no need to create variables that can never be feasible.
            if win_end_min - win_start_min < operation.duration_minutes:
                continue

            present = model.new_bool_var(f"{prefix}_on_{r.id}_w{w_idx}")
            interval = model.new_optional_interval_var(
                start,
                operation.duration_minutes,
                end,
                present,
                f"{prefix}_iv_{r.id}_w{w_idx}",
            )

            # Conditional containment: if this (resource, window) is chosen, the op must fit fully inside this window.
            model.add(start >= win_start_min).only_enforce_if(present)
            model.add(end <= win_end_min).only_enforce_if(present)

            presences[(r.id, w_idx)] = present
            intervals[(r.id, w_idx)] = interval

    if not presences:
        # Every eligible resource's every window is too short.
        raise InfeasibleError(
            [
                f"no working window long enough for {product.id} step {step_index} "
                f"({operation.duration_minutes} min on capability '{operation.capability}')"
            ]
        )

    model.add_exactly_one(list(presences.values()))

    return _OpVars(
        product_id=product.id,
        step_index=step_index,
        capability=operation.capability,
        duration=operation.duration_minutes,
        start=start,
        end=end,
        presences=presences,
        intervals=intervals,
    )


def _add_precedence_constraints(
    model: cp_model.CpModel,
    op_vars: list[_OpVars],
    products: tuple[Product, ...],
) -> None:
    "Each step in a product's route starts at or after the previous step ends."
    by_product: dict[str, list[_OpVars]] = {p.id: [] for p in products}
    for ov in op_vars:
        by_product[ov.product_id].append(ov)

    for steps in by_product.values():
        steps.sort(key=lambda ov: ov.step_index)
        for prev, curr in zip(steps, steps[1:]):
            model.add(curr.start >= prev.end)


def _add_min_tardiness_objective(
    model: cp_model.CpModel,
    op_vars: list[_OpVars],
    problem: SchedulingProblem,
    horizon_end_min: int,
) -> None:
    "Minimize sum over products of max(0, last_op.end - due)."
    last_op_by_product: dict[str, _OpVars] = {}
    for ov in op_vars:
        prev = last_op_by_product.get(ov.product_id)
        if prev is None or ov.step_index > prev.step_index:
            last_op_by_product[ov.product_id] = ov

    tardiness_vars: list[cp_model.IntVar] = []
    for product in problem.products:
        last = last_op_by_product[product.id]
        due_min = to_minutes(product.due, problem.horizon.start)
        # tardiness = max(0, end - due)
        tardiness = model.new_int_var(0, horizon_end_min, f"tardy_{product.id}")
        model.add(tardiness >= last.end - due_min)
        # tardiness >= 0 is implicit from the var's lower bound.
        tardiness_vars.append(tardiness)

    model.minimize(sum(tardiness_vars))


def _extract_solution(
    solver: cp_model.CpSolver,
    op_vars: list[_OpVars],
    horizon_start,
) -> Solution:
    "Pull the chosen assignments out of the solver."
    assignments: list[Assignment] = []
    for ov in op_vars:
        chosen_resource = None
        for (resource_id, _w_idx), present in ov.presences.items():
            if solver.boolean_value(present):
                chosen_resource = resource_id
                break
        assert (
            chosen_resource is not None
        ), "AddExactlyOne should guarantee one resource"

        start_min = solver.value(ov.start)
        end_min = solver.value(ov.end)
        assignments.append(
            Assignment(
                product_id=ov.product_id,
                step_index=ov.step_index,
                capability=ov.capability,
                resource_id=chosen_resource,
                start=from_minutes(start_min, horizon_start),
                end=from_minutes(end_min, horizon_start),
            )
        )

    # Deterministic output: sort by (start, product, step) so identical inputs produce identical responses regardless of dict iteration order.
    assignments.sort(key=lambda a: (a.start, a.product_id, a.step_index))
    return Solution(assignments=tuple(assignments))
