from ortools.sat.python import cp_model

from app.domain.problem import SchedulingProblem
from app.objectives.base import register
from app.solvers._op_vars import OpVars


def add_to_model(
    model: cp_model.CpModel,
    op_vars: list[OpVars],
    problem: SchedulingProblem,
) -> None:
    # Group ops by which resources they could potentially run on.
    ops_per_resource: dict[str, list[OpVars]] = {}
    for ov in op_vars:
        seen_resources = set()
        for r_id, _w in ov.presences:
            if r_id in seen_resources:
                continue
            seen_resources.add(r_id)
            ops_per_resource.setdefault(r_id, []).append(ov)

    same_family_adjacencies: list[cp_model.IntVar] = []

    for r_id, ops in ops_per_resource.items():
        if len(ops) < 2:
            continue

        # Node 0 = source/sink. Ops are 1..n.
        arcs: list[tuple[int, int, cp_model.IntVar]] = []

        # Self-loops: op_i skips the resource (i.e. is placed elsewhere).
        for i, ov in enumerate(ops, start=1):
            on_r = _resource_presence(model, ov, r_id)
            not_on_r = model.new_bool_var(f"skip_{ov.product_id}_s{ov.step_index}_{r_id}")
            model.add(not_on_r + on_r == 1)
            arcs.append((i, i, not_on_r))

        # Source <-> op edges: every op needs a first/last arc.
        for i, ov in enumerate(ops, start=1):
            first = model.new_bool_var(f"first_{ov.product_id}_s{ov.step_index}_{r_id}")
            last = model.new_bool_var(f"last_{ov.product_id}_s{ov.step_index}_{r_id}")
            arcs.append((0, i, first))
            arcs.append((i, 0, last))

        # Adjacency arcs: i -> j means op j immediately follows op i on r.
        for i, ov_i in enumerate(ops, start=1):
            for j, ov_j in enumerate(ops, start=1):
                if i == j:
                    continue
                follows = model.new_bool_var(
                    f"adj_{ov_i.product_id}_s{ov_i.step_index}_then_"
                    f"{ov_j.product_id}_s{ov_j.step_index}_{r_id}"
                )
                arcs.append((i, j, follows))

                # This is the payload: if the arc is true and families match,
                # count it. Solver decides which arcs to activate.
                if ov_i.family == ov_j.family:
                    same_family_adjacencies.append(follows)

        model.add_circuit(arcs)

    if same_family_adjacencies:
        model.maximize(sum(same_family_adjacencies))
    else:
        model.maximize(0)


def _resource_presence(model, ov, resource_id):
    window_presences = [p for (r_id, _), p in ov.presences.items() if r_id == resource_id]
    if len(window_presences) == 1:
        return window_presences[0]
    on_r = model.new_bool_var(f"on_{ov.product_id}_s{ov.step_index}_{resource_id}")
    model.add_bool_or(window_presences).only_enforce_if(on_r)
    for p in window_presences:
        model.add_implication(p, on_r)
    return on_r


register("max_family_batching", add_to_model)