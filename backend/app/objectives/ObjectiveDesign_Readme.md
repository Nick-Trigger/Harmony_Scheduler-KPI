# Objectives - Design Reference

This document describes the internal data structures objective functions operate on. Read this before writing a new objective.

The contract for an objective function is fixed:

```python
def add_to_model(
    model: cp_model.CpModel,
    op_vars: list[OpVars],
    problem: SchedulingProblem,
) -> None:
    ...
```

The function mutates `model` in place by adding decision variables, then calling `model.minimize(...)` or `model.maximize(...)`. It does not return a value.

## `model: cp_model.CpModel`

The OR-Tools CP-SAT model being built. By the time an objective function runs, the model already contains:

- All operation start, end, and interval variables (from `solvers/cpsat.py`)
- No-overlap constraints per resource
- Precedence constraints within each product's route
- Calendar containment constraints (via `only_enforce_if`)
- Family changeover setup-time constraints (via the disjunctive pattern)

The objective is added *last*, after all hard constraints are in place.

Useful methods for objective functions:

| Method | Returns | Use |
|--|--|--|
| `new_int_var(lo, hi, name)` | `IntVar` | Create a new integer variable |
| `new_bool_var(name)` | `IntVar` (used as bool) | Create a new boolean variable |
| `add(linear_expr)` | constraint | Add a linear constraint (e.g., `x >= y + 5`) |
| `add_bool_or(literals)` | constraint | OR over a list of booleans |
| `add_implication(a, b)` | constraint | If a is true, b is true |
| `add_circuit(arcs)` | constraint | Hamiltonian circuit over `[(from, to, literal)]` triples |
| `minimize(expr)` | none | Set the objective to minimize |
| `maximize(expr)` | none | Set the objective to maximize |

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

Example access:

```python
horizon_end_min = (problem.horizon.end - problem.horizon.start).total_seconds() / 60
my_var = model.new_int_var(0, int(horizon_end_min), "my_var")
model.add(my_var >= ov.end)   # works directly - start/end are IntVars
```

`duration` is the integer number of minutes the operation takes. It's a constant (not a variable) - `model.add(end == start + duration)` is already enforced by the solver.

### Resource assignment

`presences` is a dict from `(resource_id, window_index)` to a boolean variable. The boolean is `True` if this operation runs on that specific window of that specific resource. Across all `(resource, window)` pairs for a given operation, exactly one is `True` (enforced by `add_exactly_one` in `solvers/cpsat.py`).

To check if an op is on a specific resource (ignoring which window):

```python
# True if any window-presence on resource_id is true
on_resource = [p for (r_id, _), p in ov.presences.items() if r_id == resource_id]
# Then OR them together - see resource_presence helper in min_changeovers.py
```

`intervals` is the same structure but stores CP-SAT `IntervalVar`s - these are what get passed to `add_no_overlap` per resource. You typically don't need these in an objective; they're consumed by the solver's constraint layer.

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

To find a product by ID:

```python
products_by_id = {p.id: p for p in problem.products}
product = products_by_id[some_id]
```

Use `product.due` (a datetime) and convert with `to_minutes` to get integer minutes for use in constraints.

To get a product's last operation in `op_vars`:

```python
last_op_by_product: dict[str, OpVars] = {}
for ov in op_vars:
    prev = last_op_by_product.get(ov.product_id)
    if prev is None or ov.step_index > prev.step_index:
        last_op_by_product[ov.product_id] = ov
```

### `problem.changeover_matrix`

```python
@dataclass(frozen=True)
class ChangeoverMatrix:
    values: dict[tuple[Family, Family], int]

    def setup_minutes(self, from_family: Family, to_family: Family) -> int: # Gets the setup time between family transitions
        ...
```

><p><span style="color: #E63946;"><strong>IMPORTANT</strong></span>: Always use the `setup_minutes` method rather than `values.get(...)` directly - it correctly returns 0 for same-family transitions even when the entry is missing from the dict.</p>

### `problem.settings`

```python
@dataclass(frozen=True)
class SolverSettings:
    time_limit_seconds: int
    objective_mode: str
```

Generally not needed inside an objective function; the solver applies `time_limit_seconds` itself, and `objective_mode` is what selected this function in the first place.

## Time conversion

Datetimes to and from integer minutes since horizon. Defined in `solvers/_time.py`:

```python
def to_minutes(t: datetime, origin: datetime) -> int:
    """Convert a datetime to integer minutes since `origin`."""

def from_minutes(m: int, origin: datetime) -> datetime:
    """Convert integer minutes since `origin` back to a datetime."""
```

><p><span style="color: #E63946;"><strong>IMPORTANT</strong></span>: Always use `problem.horizon.start` as the origin. The solver's start/end variables are minutes since that origin. </p>

```python
from app.solvers._time import to_minutes

due_min = to_minutes(product.due, problem.horizon.start)
model.add(some_var <= due_min)
```

## Example: minimum boilerplate ([min_makespan](./min_makespan.py))

A trivial objective that minimizes the total processing time of the longest product (a constant - solver will just compute it):

```python
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
```

Then in [`__init__.py`](./__init__.py) in the `objectives` folder:

```python
# Add new objective here. They are automatically registered at import time.
[...] #other imports
from app.objectives import min_makespan
```

This objective creates one new integer variable, constrains it to be at least as large as every op's end time, and minimizes it. The solver naturally drives it down to the latest end, which becomes the schedule's finish time.

Note what this function did *and* didn't touch:

- Used `op_vars[i].end` (read-only access to existing variables)
- Used `problem.horizon` to bound the new variable
- Added one new variable and `len(op_vars)` new constraints
- Did not modify any existing variable, did not touch `domain/`, did not edit `cpsat.py`

## Common patterns

### Counting events with booleans

To count something (changeovers, tardy products, idle resources), define booleans and minimize their sum:

```python
flags = []
for ov in op_vars:
    flag = model.new_bool_var(f"{ov.product_id}_tardy")
    due_min = to_minutes(...)
    # flag is true if this op ends late
    model.add(ov.end > due_min).only_enforce_if(flag)
    model.add(ov.end <= due_min).only_enforce_if(flag.Not())
    flags.append(flag)
model.minimize(sum(flags))
```

### Summing over conditions with `only_enforce_if`

To enforce a constraint conditionally on a boolean:

```python
some_constraint = model.add(x >= y + 5)
some_constraint.only_enforce_if(condition_bool)
```

Multiple conditions:

```python
model.add(x >= y).only_enforce_if([cond_a, cond_b])  # both must be true
```

### Adjacency on a shared resource

To know whether op A and op B are placed on the same resource *and* B immediately follows A (with no other op between them), use `add_circuit`. This is the cleanest CP-SAT pattern for "immediate successor" reasoning.

The mental model: for each resource, build a directed graph where:

- Node 0 is a virtual source/sink
- Nodes 1..n are the operations potentially on this resource
- Arcs represent "could be the next thing"

`add_circuit` then enforces that the active arcs form exactly one
Hamiltonian circuit through participating nodes. An arc `(i, j)` being
true means **op j immediately follows op i**.

#### Required arcs

Three kinds of arcs make the circuit valid:

| Arc | Meaning | When the literal is true |
|--|--|--|
| `(0, i, first_i)` | Source &rarr; op i | Op i is the first on this resource |
| `(i, 0, last_i)` | Op i &rarr; sink | Op i is the last on this resource |
| `(i, i, skip_i)` | Op i self-loop | Op i is **not** on this resource |
| `(i, j, follows_ij)` | Op i &rarr; op j | Op j runs immediately after op i |

The self-loop is the trick that makes this work: ops not assigned to this resource take their self-loop and effectively drop out of the circuit. Ops that *are* on the resource thread through via source &rarr; ... &rarr; sink.

#### Minimal example: count gaps between same-family ops

Suppose you want to maximize the number of times two same-family ops run back-to-back on the same resource (the opposite of `min_changeovers`).

```python
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
            on_r = resource_presence(model, ov, r_id)
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


def resource_presence(model, ov, resource_id):
    window_presences = [p for (r_id, _), p in ov.presences.items() if r_id == resource_id]
    if len(window_presences) == 1:
        return window_presences[0]
    on_r = model.new_bool_var(f"on_{ov.product_id}_s{ov.step_index}_{resource_id}")
    model.add_bool_or(window_presences).only_enforce_if(on_r)
    for p in window_presences:
        model.add_implication(p, on_r)
    return on_r


register("max_family_batching", add_to_model)
```

#### Reading the arcs after solving

After the solver returns, you can iterate the arcs to see which followed which:

```python
solver = cp_model.CpSolver()
solver.solve(model)

for r_id, arc_vars_by_resource in stored_arcs.items():
    for (i, j, var) in arc_vars_by_resource:
        if i != j and i != 0 and j != 0 and solver.boolean_value(var):
            print(f"On {r_id}: op {i} immediately followed by op {j}")
```

(You'd need to store the arc-to-op mapping during model building if you want to interpret results — `solvers/cpsat.py::_extract_solution` does similar bookkeeping for the presence booleans.)

#### Why not pairwise "before" booleans

For setup-time *enforcement*, the disjunctive pattern (one boolean per unordered pair, gated by `only_enforce_if`) is simpler than `add_circuit`. That's what `solvers/cpsat.py::_add_changeover_constraints` uses.

For *counting adjacencies*, the disjunctive pattern doesn't work because "A is before B" is true for non-adjacent pairs too. You'd over-count. `add_circuit` gives exact adjacency for free.

Rule of thumb:

- **Setup-time enforcement** &rarr; disjunctive pattern (cheaper)
- **Adjacency counting** &rarr; `add_circuit` (exact)

## What to avoid

- **Don't reassign or modify any existing `OpVars` field.** They're frozen and used by the solver.
- **Don't add constraints that conflict with the hard constraints.** The model is over-determined and won't solve.
- **Don't pass non-integer values to `model.add`.** Use integer minutes throughout. Floats break CP-SAT.
- **Don't iterate over `presences` keys assuming they're unique resource IDs.** They're `(resource_id, window_index)` tuples - multiple keys can share the same resource.
