"""Shared helpers used by both constraint modules and objective modules.

Lives under solvers/ because both consumers (constraints, objectives) speak
the same CP-SAT vocabulary that OpVars exposes. Keeping the helper here
avoids a circular dependency between constraints/ and objectives/.
"""

from ortools.sat.python import cp_model

from app.solvers._op_vars import OpVars


def resource_presence(
    model: cp_model.CpModel,
    ov: OpVars,
    resource_id: str,
) -> cp_model.IntVar:
    """Return a BoolVar that is true iff `ov` is placed on `resource_id`.

    An op may have multiple per-window presence booleans for the same
    resource. This helper exposes a single "on this resource at all"
    boolean to consumers that don't care about which window.
    """
    window_presences = [
        p for (r_id, _), p in ov.presences.items() if r_id == resource_id
    ]

    if len(window_presences) == 1:
        return window_presences[0]

    on_r = model.new_bool_var(
        f"on_{ov.product_id}_s{ov.step_index}_{resource_id}"
    )
    model.add_bool_or(window_presences).only_enforce_if(on_r)
    for p in window_presences:
        model.add_implication(p, on_r)
    return on_r