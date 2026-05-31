# Constraints - Design Reference

This document describes the internal data structures constraint modules operate on. Read this before writing a new constraint.

A constraint owns both its **model-side enforcement** (added to the CP-SAT model before solving) and its **post-solve validation** (an independent re-check against the final solution). Keeping both halves in one module means a change to enforcement is co-located with the verification that proves it.

The contract for a constraint is a class implementing the `Constraint` protocol:

```python
class MyConstraint:
    name: str  # for diagnostics and ordering

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        ...

    def validate(
        self,
        solution: Solution,
        problem: SchedulingProblem,
    ) -> None:
        ...
```

`add_to_model` mutates `model` in place by adding constraints. `validate` reads the final `Solution` and raises `InvariantError` if the constraint is violated. Neither returns a value.

Registration happens at module load time via `register(MyConstraint())` at the bottom of the file.

## `model: cp_model.CpModel`

The OR-Tools CP-SAT model being built. By the time a constraint's `add_to_model` runs, the model already contains:

- All operation start, end, and interval variables (from `solvers/cpsat.py::_build_op_vars`)
- Per-window optional intervals and presence booleans
- `add_exactly_one` constraints selecting one (resource, window) per op

Constraints are applied **after** OpVars construction and **before** the objective. The order of application within the constraint pass is the registration order in `constraints/__init__.py`.

Useful methods for constraints:

| Method | Returns | Use |
|--|--|--|
| `add(linear_expr)` | constraint | Add a linear constraint (e.g., `x >= y + 5`) |
| `new_bool_var(name)` | `IntVar` (used as bool) | Create a new boolean variable |
| `new_int_var(lo, hi, name)` | `IntVar` | Create a new integer variable |
| `add_no_overlap(intervals)` | constraint | Disallow overlap among interval variables |
| `add_bool_or(literals)` | constraint | OR over a list of booleans |
| `add_implication(a, b)` | constraint | If a is true, b is true |

For the full API, see the [OR-Tools CP-SAT docs](https://developers.google.com/optimization/cp/cp_solver).

## `op_vars: list[OpVars]`

A flat list of one `OpVars` per operation across all products. Defined in `solvers/_op_vars.py`:

```python
@dataclass
class OpVars:
    product_id: str
    step_index: int
    capability: str
    family: str
    duration: int

    start: cp_model.IntVar
    end: cp_model.IntVar

    presences: dict[tuple[str, int], cp_model.IntVar]
    intervals: dict[tuple[str, int], cp_model.IntervalVar]
```

### Identification

`product_id` and `step_index` together identify the operation uniquely. `step_index` is **1-based**, matching the wire format. Within a single product's route, step indices are contiguous starting from 1.

### Timing

`start` and `end` are integer variables representing **minutes since horizon start**. The horizon's start time is `problem.horizon.start`; to convert back to absolute datetimes, see `solvers/_time.py::from_minutes`.

`duration` is the integer number of minutes the operation takes. `end == start + duration` is already enforced by the solver.

### Resource assignment

`presences` is a dict from `(resource_id, window_index)` to a boolean variable. The boolean is `True` if this operation runs on that specific window of that specific resource. Across all `(resource, window)` pairs for a given operation, exactly one is `True` (enforced by `add_exactly_one` in `solvers/cpsat.py`).

To check if an op is on a specific resource (ignoring which window), use the shared helper:

```python
from app.solvers._helpers import resource_presence
on_r = resource_presence(model, ov, "Fill-1")  # bool var: true iff ov is on Fill-1
```

`intervals` is the same structure but stores CP-SAT `IntervalVar`s - these are passed to `add_no_overlap` per resource. Constraints that operate on time ranges (no-overlap, calendar containment) work with these.

### Family

`family` is the family string from `problem.products[i].family` for the product that owns this op. Available directly on the `OpVars` to save you a lookup. Used in changeover decisions.

## `problem: SchedulingProblem`

The full canonical problem from `domain/problem.py`. Frozen dataclasses throughout - safe to read, can't be mutated.

```python
@dataclass(frozen=True)
class SchedulingProblem:
    horizon: Horizon
    resources: tuple[Resource, ...]
    products: tuple[Product, ...]
    changeover_matrix: ChangeoverMatrix
    settings: SolverSettings
```

### `problem.horizon`

```python
@dataclass(frozen=True)
class Horizon:
    start: datetime
    end: datetime
```

Use `problem.horizon.start` as the anchor for `to_minutes` / `from_minutes` conversions.

### `problem.resources`

Tuple of `Resource` objects:

```python
@dataclass(frozen=True)
class Resource:
    id: str
    capabilities: frozenset[Capability]
    calendar: tuple[WorkingWindow, ...]
```

`capabilities` is a frozenset of strings. `calendar` is a tuple of working windows (each with `start` and `end` datetimes).

### `problem.products`

Tuple of `Product` objects:

```python
@dataclass(frozen=True)
class Product:
    id: str
    family: Family
    due: datetime
    route: tuple[Operation, ...]
```

### `problem.changeover_matrix`

```python
@dataclass(frozen=True)
class ChangeoverMatrix:
    values: dict[tuple[Family, Family], int]

    def setup_minutes(self, from_family: Family, to_family: Family) -> int:
        ...
```

><p><span style="color: #E63946;"><strong>IMPORTANT</strong></span>: Always use the `setup_minutes` method rather than `values.get(...)` directly - it correctly returns 0 for same-family transitions even when the entry is missing from the dict.</p>

### `problem.settings`

Generally not needed inside a constraint; the solver applies `time_limit_seconds` itself, and `objective_mode` is for objective selection.

## `solution: Solution`

Passed to `validate` after solving. Defined in `domain/solution.py`:

```python
@dataclass(frozen=True)
class Solution:
    assignments: tuple[Assignment, ...]


@dataclass(frozen=True)
class Assignment:
    product_id: str
    step_index: int
    capability: str
    resource_id: str
    start: datetime
    end: datetime
```

Validation reads concrete datetime values from `Assignment`, unlike enforcement which works with CP-SAT variables. Common validation pattern:

```python
# Group assignments by some key
by_resource: dict[str, list[Assignment]] = {}
for a in solution.assignments:
    by_resource.setdefault(a.resource_id, []).append(a)

# Walk pairs in time order
for r_id, assignments in by_resource.items():
    assignments.sort(key=lambda a: a.start)
    for prev, curr in zip(assignments, assignments[1:]):
        if some_violation(prev, curr):
            raise InvariantError(f"violation on {r_id}: ...")
```

## `InvariantError`

Defined in `app/constraints/base.py`. Re-exported from `app/validation.py` for convenience.

```python
class InvariantError(Exception):
    """Raised when a Solution violates a hard constraint.

    Distinct from InfeasibleError: this means the solver produced
    an invalid output (a bug), not that no solution exists.
    """
```

`api/errors.py` maps `InvariantError` to a **500 Internal Server Error** because, if validation fails on the solver's output, that's a bug in our model — not a user error.

## Time conversion

Datetimes to and from integer minutes since horizon. Defined in `solvers/_time.py`:

```python
def to_minutes(t: datetime, origin: datetime) -> int:
    """Convert a datetime to integer minutes since `origin`."""

def from_minutes(m: int, origin: datetime) -> datetime:
    """Convert integer minutes since `origin` back to a datetime."""
```

><p><span style="color: #E63946;"><strong>IMPORTANT</strong></span>: Always use `problem.horizon.start` as the origin. The solver's start/end variables are minutes since that origin.</p>

```python
from app.solvers._time import to_minutes

due_min = to_minutes(product.due, problem.horizon.start)
model.add(some_var <= due_min)
```

## Example: minimum boilerplate ([precedence](./precedence.py))

The precedence constraint — step n+1 cannot start before step n ends — is the smallest non-trivial example. Both halves of the constraint are visible:

```python
from ortools.sat.python import cp_model

from app.constraints.base import InvariantError, register
from app.domain.problem import SchedulingProblem
from app.domain.solution import Assignment, Solution
from app.solvers._op_vars import OpVars


class PrecedenceConstraint:
    """Step n+1 of a product's route cannot start before step n ends."""

    name = "precedence"

    def add_to_model(
        self,
        model: cp_model.CpModel,
        op_vars: list[OpVars],
        problem: SchedulingProblem,
    ) -> None:
        by_product: dict[str, list[OpVars]] = {}
        for ov in op_vars:
            by_product.setdefault(ov.product_id, []).append(ov)

        for steps in by_product.values():
            steps.sort(key=lambda ov: ov.step_index)
            for prev, curr in zip(steps, steps[1:]):
                model.add(curr.start >= prev.end)

    def validate(
        self,
        solution: Solution,
        problem: SchedulingProblem,
    ) -> None:
        by_product: dict[str, list[Assignment]] = {}
        for a in solution.assignments:
            by_product.setdefault(a.product_id, []).append(a)

        for product_id, assignments in by_product.items():
            assignments.sort(key=lambda a: a.step_index)
            for prev, curr in zip(assignments, assignments[1:]):
                if curr.start < prev.end:
                    raise InvariantError(
                        f"precedence violation in {product_id}: "
                        f"step {curr.step_index} starts before "
                        f"step {prev.step_index} ends"
                    )


register(PrecedenceConstraint())
```

Then in [`__init__.py`](./__init__.py) in the `constraints` folder:

```python
# Add new constraint here. They are automatically registered at import time.
[...] #other imports
import app.constraints.precedence  # noqa: F401
```

Note the symmetry: `add_to_model` adds `curr.start >= prev.end` as a CP-SAT constraint, and `validate` checks the same relationship against concrete datetimes. The two halves prove the constraint at both ends of the pipeline.

What this constraint did *and* didn't touch:

- Used `op_vars[i].start` and `op_vars[i].end` (read-only access to existing variables) in enforcement
- Used `solution.assignments[i].start` and `.end` (read-only access to concrete values) in validation
- Did not modify any existing variable, did not touch `domain/`, did not edit `cpsat.py` or `validation.py`

## Constraints with no model-side enforcement

Some constraints (eligibility, duration, calendar, horizon) are enforced **intrinsically** during `OpVars` construction in `solvers/cpsat.py::_build_op_vars`:

- **Eligibility**: presence vars are only created for resources providing the capability
- **Duration**: `model.add(end == start + duration_minutes)` is added during op construction
- **Calendar**: per-window intervals carry conditional containment constraints
- **Horizon**: start/end vars are bounded at `[0, horizon_end_min]` by domain

These constraints still get their own modules in `constraints/`, but their `add_to_model` is a **no-op** (`return`). The module exists for two reasons:

1. **Validation** — even when enforcement is intrinsic, an independent post-solve check is valuable defense in depth against solver bugs.
2. **Documentation** — the constraint appearing in the registry makes the system's hard constraints discoverable in one place, even when their enforcement happens elsewhere.

When writing a new constraint, ask: *can it be enforced as a property of how OpVars are built?* If yes, edit `_build_op_vars` and use the constraint module only for validation. If no (the constraint wraps around already-built OpVars — like no-overlap or precedence), implement enforcement in `add_to_model`.

## Common patterns

### Pairwise constraints between ops on the same resource

When a constraint applies to pairs of ops that might share a resource (changeover setup, sequencing requirements), iterate ordered pairs and gate the constraint on resource presence:

```python
from app.solvers._helpers import resource_presence

for i, op_i in enumerate(op_vars):
    for j, op_j in enumerate(op_vars):
        if i == j:
            continue

        shared = {r for (r, _) in op_i.presences} & {r for (r, _) in op_j.presences}
        for r_id in shared:
            i_on_r = resource_presence(model, op_i, r_id)
            j_on_r = resource_presence(model, op_j, r_id)
            # Constraint applies only when both ops are actually on r
            model.add(op_j.start >= op_i.end + 10).only_enforce_if([i_on_r, j_on_r])
```

For setup-time constraints with two directions (i before j *or* j before i), use the disjunctive pattern with a single ordering boolean — see `constraints/changeover.py` for a worked example.

### Conditional constraints with `only_enforce_if`

To enforce a constraint conditionally on a boolean:

```python
some_constraint = model.add(x >= y + 5)
some_constraint.only_enforce_if(condition_bool)
```

Multiple conditions (all must be true):

```python
model.add(x >= y).only_enforce_if([cond_a, cond_b])
```

### Defensive validation

Validation should produce diagnostic messages a developer can act on — not just "constraint failed":

```python
raise InvariantError(
    f"overlap on {resource_id}: {prev.product_id} step {prev.step_index} "
    f"({prev.start.isoformat()}–{prev.end.isoformat()}) overlaps "
    f"{curr.product_id} step {curr.step_index} "
    f"({curr.start.isoformat()}–{curr.end.isoformat()})"
)
```

Include the resource, both ops, and the conflicting time ranges. A maintainer reading the test failure should know exactly which assignments to inspect.

## What to avoid

- **Don't reassign or modify any existing `OpVars` field.** They're frozen and used elsewhere in the model.
- **Don't add constraints that conflict with the hard constraints already enforced.** The model is over-determined and won't solve.
- **Don't pass non-integer values to `model.add`.** Use integer minutes throughout. Floats break CP-SAT.
- **Don't iterate over `presences` keys assuming they're unique resource IDs.** They're `(resource_id, window_index)` tuples - multiple keys can share the same resource. Use the `resource_presence` helper from `solvers/_helpers.py`.
- **Don't catch `InvariantError` inside `validate`.** Let it propagate; the validator orchestrator stops at the first violation, and that's the right behavior.
- **Don't perform expensive computation in `validate` repeatedly.** If you need to group assignments or build lookups, do it once at the top of the method.