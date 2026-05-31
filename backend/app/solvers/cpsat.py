from dataclasses import dataclass
from ortools.sat.python import cp_model

import app.constraints  # noqa: F401
import app.objectives  # noqa: F401

from app.constraints.base import all_constraints
from app.objectives.base import get as get_objective

from app.solvers.base import InfeasibleError
from app.validation import InvariantError
from app.domain.problem import Operation, Product, Resource, SchedulingProblem
from app.domain.solution import Assignment, Solution
from app.solvers._time import from_minutes, to_minutes
from app.solvers._op_vars import OpVars
from app.solvers._diagnostics import diagnose_infeasibility

import app.objectives  # registers objective functions
from app.objectives.base import get as get_objective

# %% Solver Entry


def solve(problem: SchedulingProblem) -> Solution:
    horizon_start = problem.horizon.start
    horizon_end_min = to_minutes(problem.horizon.end, horizon_start)

    model = cp_model.CpModel()

    # Build operation variables and collect them per resource for no-overlap. Horizon are enforced intrinsically here through how the variables are constructed.
    op_vars = _build_all_op_vars(model, problem, horizon_start, horizon_end_min)
    
    # Apply registered constraints to the model.
    for constraint in all_constraints():
        constraint.add_to_model(model, op_vars, problem)

    # Apply the selected objective.
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


def _build_all_op_vars(
    model: cp_model.CpModel,
    problem: SchedulingProblem,
    horizon_start,
    horizon_end_min: int,
) -> list[OpVars]:
    """Construct one OpVars per (product, step) for the whole problem."""
    op_vars: list[OpVars] = []
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
    return op_vars


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
    # ELIGIBILITY: filter to resources that provide the required capability.
    eligible = [r for r in resources if operation.capability in r.capabilities]
    if not eligible:
        raise InfeasibleError(
            [
                f"no resource has capability '{operation.capability}' "
                f"(required by {product.id} step {step_index})"
            ]
        )

    prefix = f"{product.id}_s{step_index}"

    # HORIZON: domain bounds on start and end.
    start = model.new_int_var(0, horizon_end_min, f"{prefix}_start")
    end = model.new_int_var(0, horizon_end_min, f"{prefix}_end")

    # DURATION: end is fixed offset from start.
    model.add(end == start + operation.duration_minutes)

    presences: dict[tuple[str, int], cp_model.IntVar] = {}
    intervals: dict[tuple[str, int], cp_model.IntervalVar] = {}

    for r in eligible:
        for w_idx, window in enumerate(r.working_windows):
            win_start_min = to_minutes(window.start, horizon_start)
            win_end_min = to_minutes(window.end, horizon_start)

            # Pre-filter: if window can't hold the operation, don't create
            # variables for it.
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

            # CALENDAR: if this (resource, window) is chosen, op must fit
            # entirely inside this window.
            model.add(start >= win_start_min).only_enforce_if(present)
            model.add(end <= win_end_min).only_enforce_if(present)

            presences[(r.id, w_idx)] = present
            intervals[(r.id, w_idx)] = interval

    if not presences:
        raise InfeasibleError(
            [
                f"no working window long enough for {product.id} step {step_index} "
                f"({operation.duration_minutes} min on capability "
                f"'{operation.capability}')"
            ]
        )

    # Exactly one (resource, window) must be selected.
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


def _extract_solution(
    solver: cp_model.CpSolver,
    op_vars: list[OpVars],
    horizon_start,
) -> Solution:
    "Read the solver's chosen values back into a canonical Solution."
    
    assignments: list[Assignment] = []
    for ov in op_vars:
        chosen_resource = None
        for (resource_id, _), present in ov.presences.items():
            if solver.boolean_value(present):
                chosen_resource = resource_id
                break
        assert chosen_resource is not None, (
            "add_exactly_one should guarantee one (resource, window) per op"
        )

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

    # Deterministic output ordering.
    assignments.sort(key=lambda a: (a.start, a.product_id, a.step_index))
    return Solution(assignments=tuple(assignments))
