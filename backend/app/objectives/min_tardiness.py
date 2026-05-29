from ortools.sat.python import cp_model

from app.domain.problem import SchedulingProblem
from app.objectives.base import register
from app.solvers._op_vars import OpVars
from app.solvers._time import to_minutes


def add_to_model(
    model: cp_model.CpModel,
    op_vars: list[OpVars],
    problem: SchedulingProblem,
) -> None:
    "Minimize sum over products of max(0, last_op.end - due) in minutes."
    horizon_end_min = to_minutes(problem.horizon.end, problem.horizon.start)

    last_op_by_product: dict[str, OpVars] = {}
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


# Register at import:
register("min_tardiness", add_to_model)
