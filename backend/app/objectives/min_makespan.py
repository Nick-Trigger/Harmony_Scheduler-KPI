from ortools.sat.python import cp_model

from app.domain.problem import SchedulingProblem
from app.objectives.base import register
from app.solvers._op_vars import OpVars


def add_to_model(
    model: cp_model.CpModel,
    op_vars: list[OpVars],
    problem: SchedulingProblem,
) -> None:
    "Minimize the latest end time across all operations (makespan)."

    horizon_end_min = int((problem.horizon.end - problem.horizon.start).total_seconds() / 60)
    makespan = model.new_int_var(0, horizon_end_min, "makespan")
    for ov in op_vars:
        model.add(makespan >= ov.end)
    model.minimize(makespan)


register("min_makespan", add_to_model)