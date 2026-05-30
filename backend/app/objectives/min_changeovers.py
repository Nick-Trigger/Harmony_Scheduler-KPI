from ortools.sat.python import cp_model

from app.domain.problem import SchedulingProblem
from app.objectives.base import register
from app.solvers._op_vars import OpVars


def add_to_model(
    model: cp_model.CpModel,
    op_vars: list[OpVars],
    problem: SchedulingProblem,
) -> None:
    ops_per_resource: dict[str, list[OpVars]] = {}
    for ov in op_vars:
        for r_id, _w_ix in ov.presences:
            ops_per_resource.setdefault(r_id, []).append(ov)

    # An operation cannot appear more than once in a sequence per product
    for r_id in ops_per_resource:
        seen = set()
        unique_ops = []
        for ov in ops_per_resource[r_id]:
            key = (ov.product_id, ov.step_index)
            if key not in seen:
                seen.add(key)
                unique_ops.append(ov)
        ops_per_resource[r_id] = unique_ops

    changeover_arcs: list[cp_model.IntVar] = []

    for r_id, ops in ops_per_resource.items():
        if len(ops) < 2:
            continue  # no changeovers possible with 0 or 1 operation

        # AddCircuit nodes: 0 is source/sink, 1..n are the ops
        arcs: list[tuple[int, int, cp_model.IntVar]] = []

        # Self-loop on each op: true iff op is NOT on this resource
        for i, ov in enumerate(ops, start=1):
            on_r = _resource_presence(model, ov, r_id)
            not_on_r = model.new_bool_var(
                f"not_{ov.product_id}_s{ov.step_index}_{r_id}"
            )
            model.add(not_on_r + on_r == 1)
            arcs.append((i, i, not_on_r))

        # Source → op: true iff op is first on this resource
        # Op → sink: true iff op is last on this resource
        for i, ov in enumerate(ops, start=1):
            first = model.new_bool_var(
                f"first_{ov.product_id}_s{ov.step_index}_{r_id}"
            )
            last = model.new_bool_var(
                f"last_{ov.product_id}_s{ov.step_index}_{r_id}"
            )
            arcs.append((0, i, first))
            arcs.append((i, 0, last))

        # Op_i → Op_j: true iff op_j immediately follows op_i on this resource
        # If families differ, this boolean represents one changeover.
        for i, ov_i in enumerate(ops, start=1):
            for j, ov_j in enumerate(ops, start=1):
                if i == j:
                    continue  # skip self-loop, handled above
                arc_var = model.new_bool_var(
                    f"arc_{ov_i.product_id}_s{ov_i.step_index}_to_"
                    f"{ov_j.product_id}_s{ov_j.step_index}_{r_id}"
                )
                arcs.append((i, j, arc_var))

                # The key line you were missing:
                if ov_i.family != ov_j.family:
                    changeover_arcs.append(arc_var)

        model.add_circuit(arcs)

    if changeover_arcs:
        model.minimize(sum(changeover_arcs))
    else:
        model.minimize(0)


def _resource_presence(
    model: cp_model.CpModel,
    op_vars: OpVars,
    resource_id: str,
) -> cp_model.IntVar:
    "return a BoolVar = true if 'op_vars' is assigned to 'resource_id' on any window, false otherwise."

    window_presences = [
        p for (r_id, _), p in op_vars.presences.items() if r_id == resource_id
    ]

    if len(window_presences) == 1:
        return window_presences[0]

    on_r = model.new_bool_var(
        f"{op_vars.product_id}_s{op_vars.step_index}_{resource_id}"
    )

    model.add_bool_or(window_presences).only_enforce_if(on_r)
    for p in window_presences:
        model.add_implication(p, on_r)
    return on_r


register("min_changeovers", add_to_model)