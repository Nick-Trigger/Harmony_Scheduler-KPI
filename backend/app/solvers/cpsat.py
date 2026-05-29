from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.solvers.base import InfeasibleError
from app.domain.problem import Operation, Product, Resource, SchedulingProblem
from app.domain.solution import Assignment, Solution
from app.solvers._time import from_minutes, to_minutes
from app.solvers._op_vars import OpVars

import app.objectives #registers objective functions
from app.objectives.base import get as get_objective


# %% Solver Entry


def solve(problem: SchedulingProblem) -> Solution:
    horizon_start = problem.horizon.start
    horizon_end_min = to_minutes(problem.horizon.end, horizon_start)

    model = cp_model.CpModel()

    # Build operation variables and collect them per resource for no-overlap.
    op_vars: list[OpVars] = [] 
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
            for (resource_id, _), interval in ov.intervals.items():
                intervals_per_resource[resource_id].append(interval)

    # --- Constraint: precedence within each product's route ---
    _add_precedence_constraints(model, op_vars, problem.products)

    # --- Constraint: no overlap on each resource ---
    for intervals in intervals_per_resource.values():
        if intervals:
            model.add_no_overlap(intervals)
            
    # --- Constraint: changeover times ---
    _add_changeover_constraints(model, op_vars, problem)

    # --- Objective: pluggable via objective_mode ---
    objective_fn = get_objective(problem.settings.objective_mode)
    objective_fn(model, op_vars, problem)

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
) -> OpVars:
    eligible = [r for r in resources if operation.capability in r.capabilities]
    if not eligible:
        raise InfeasibleError(
            [
                f"no resource has capability '{operation.capability}' (required by {product.id} step {step_index})"
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
                f"no working window long enough for {product.id} step {step_index} ({operation.duration_minutes} min on capability '{operation.capability}')"
            ]
        )

    model.add_exactly_one(list(presences.values()))

    return OpVars(
        product_id=product.id,
        step_index=step_index,
        capability=operation.capability,
        family=product.family,
        duration=operation.duration_minutes,
        start=start,
        end=end,
        presences=presences,
        intervals=intervals,
    )


def _add_precedence_constraints(
    model: cp_model.CpModel,
    op_vars: list[OpVars],
    products: tuple[Product, ...],
) -> None:
    "Each step in a product's route starts at or after the previous step ends."
    by_product: dict[str, list[OpVars]] = {p.id: [] for p in products}
    for ov in op_vars:
        by_product[ov.product_id].append(ov)

    for steps in by_product.values():
        steps.sort(key=lambda ov: ov.step_index)
        for prev, curr in zip(steps, steps[1:]):
            model.add(curr.start >= prev.end)

def _resource_presence(model: cp_model.CpModel, op_vars: OpVars, resource_id: str) -> cp_model.IntVar:
    "return a BoolVar = true if 'op_vars' is assigned to 'resource_id' on any window, false otherwise."
    
    window_presences = [p for (r_id, _), p in op_vars.presences.items() if r_id == resource_id]
    
    if len(window_presences) == 1:
        return window_presences[0]
    
    on_r = model.new_bool_var(f"{op_vars.product_id}_s{op_vars.step_index}_{resource_id}") 

    # If any of the window presences is true, then on_r is true. If on_r is true, then at least one of the window presences must be true.
    model.add_bool_or(window_presences).only_enforce_if(on_r)
    for p in window_presences:
        model.add_implication(p, on_r)
    return on_r

def _add_changeover_constraints(
    model: cp_model.CpModel,
    op_vars: list[OpVars],
    problem: SchedulingProblem,
) -> None:
    """
    Enforce family-dependent setup time between ops on the same resource.

    For each ordered pair (i, j) and each resource r that both can run on,
    if i is on r AND j is on r AND i precedes j, then
        j.start >= i.end + setup(i.family, j.family).

    Same-family transitions have setup = 0, so the constraint reduces to the
    no-overlap requirement already enforced elsewhere.
    """

    matrix = problem.changeover_matrix
    n = len(op_vars)

    for i in range(n):
        for j in range(i+1, n):
            op_i = op_vars[i]
            op_j = op_vars[j]
            
            if op_i.product_id == op_j.product_id:  # handled by precedence constraints; also it is not possible for ops to share a resource if they are from the same product, since each product's route is sequential.
                continue
            
            # resource where both ops can run
            common_resources = {r_id for (r_id, _) in op_i.presences} & {r_id for (r_id, _) in op_j.presences}
            if not common_resources:
                continue
            
            setup_ij = matrix.setup_minutes(op_i.family, op_j.family)
            setup_ji = matrix.setup_minutes(op_j.family, op_i.family)
            if setup_ij == 0 and setup_ji == 0:
                continue  # no need to add a constraint for same-family transitions, since the no-overlap constraint already enforces that.
            
            for r_id in common_resources:
                i_on_r = _resource_presence(model, op_i, r_id)  # is op_i present on r?
                j_on_r = _resource_presence(model, op_j, r_id)  # is op_j present on r?
                i_before_j = model.new_bool_var(  # is op_i scheduled before op_j on r?
                    f"co_{op_i.product_id}s{op_i.step_index}_before_{op_j.product_id}_s{op_j.step_index}_on_{r_id}"
                )
                
                # if both ops are on r and op_i is the earlier one, enforce setup before op_j
                if setup_ij > 0:
                    model.add(
                        op_j.start >= op_i.end + setup_ij
                    ).only_enforce_if([i_on_r, j_on_r, i_before_j])
                    
                # if both ops are on r and op_j is the earlier one, enforce setup before op_i
                if setup_ji > 0:
                    model.add(
                        op_i.start >= op_j.end + setup_ji
                    ).only_enforce_if([i_on_r, j_on_r, i_before_j.Not()])


def _extract_solution(
    solver: cp_model.CpSolver,
    op_vars: list[OpVars],
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
