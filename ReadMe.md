# Harmony Scheduler / KPI

A constraint-based production scheduling service. Accepts a job-shop scheduling problem as JSON, returns a feasible schedule that minimizes total tardiness, and reports KPIs. Includes a React frontend with a Gantt visualization.

Built for the Harmony take-home; structured for extensibility (new client input/output formats, new objectives, new constraints) per the spec's design expectations (see [design notes](#design-notes)).

[![CI](https://github.com/Nick-Trigger/Harmony_Scheduler-KPI/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Nick-Trigger/Harmony_Scheduler-KPI/actions/workflows/ci.yml)

## Tech stack

- **Backend**: Python 3.12, FastAPI, OR-Tools CP-SAT, managed with [uv](https://github.com/astral-sh/uv)
- **Frontend**: React 19 + TypeScript with the [React Compiler](https://react.dev/learn/react-compiler), built with Vite. TailwindCSS v4 + daisyUI v5 for styling.
- **Visualization**: hand-rolled inline SVG Gantt with per-product color coding via MapTiler's `ColorRampCollection`
- **CI**: GitHub Actions runs the test suite on push and PR

## Prerequisites

- [Python 3.12+](https://www.python.org/) (managed automatically by `uv`)
- [uv](https://github.com/astral-sh/uv)
- [Node.js 22 LTS](https://nodejs.org/)

The following are pulled in automatically by `uv sync` (backend) and `npm install` during [first time setup](#first-time-setup):

- [OR-Tools (CP-SAT solver)](https://developers.google.com/optimization/)
- [TailwindCSS v4](https://tailwindcss.com)
  - [daisyUI v5 (TailwindCSS Plugin)](daisyui.com)
- [MapTiler SDK JS](https://docs.maptiler.com/sdk-js/)

### Installing Prerequisites

#### macOS / Linux

**Python 3.12+**: check if installed with `python3 --version`. If not installed:

- macOS: `brew install python@3.12`
- Linux: `sudo apt install python3.12` (Ubuntu/Debian) or use your package manager

**uv:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Node.js 22 LTS:**

- macOS: `brew install node@22`
- Linux: use [nvm](https://github.com/nvm-sh/nvm) or your package manager

#### Windows

**Python 3.12+** - check if installed with `python3 --version`. If not Installed:

Download from [python.org](https://www.python.org/downloads/) or:

```powershell
winget install Python.Python.3.12
```

**uv:**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Node.js 22 LTS** - download from [nodejs.org](https://nodejs.org/) or:

```powershell
winget install OpenJS.NodeJS.LTS
```

If PowerShell scripts won't run, enable them once per user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Running the service

### First-time setup

From the repo root:

```powershell
# Backend dependencies
cd backend
uv sync
cd ..

# Frontend dependencies
cd frontend
npm install
cd ..
```

### After Setup

#### Start the backend

```powershell
cd backend
uv run uvicorn app.main:app
```

The API reference will be available at [http://localhost:8000].
Also see [API Documentation](#api-documentation) and [Using the API](#using-the-api).

#### Start the frontend

In a separate terminal:

```powershell
cd frontend
npm run dev
```

The frontend UI will be available at [http://localhost:5173].

> Note: You do not need to run the frontend to use the backend. The API is usable independently (for example via curl or Postman. See [Using the API](#using-the-api)).

## Running the tests

From `backend/`:

```powershell
uv run pytest -v
```

The test suite includes the three tests required by the spec:

- **Invariant test** (`test_validation.py`) - validation rejects overlap and precedence violations
- **KPI test** (`test_kpis.py`) - tardiness, changeovers, makespan math against hand-crafted schedules
- **Infeasibility test** (`test_api.py`) - `POST /schedule` returns 422 with concrete reasons when the problem can't be solved

Tests run automatically on every push and pull request via GitHub Actions
(`.github/workflows/ci.yml`). [![CI](https://github.com/Nick-Trigger/Harmony_Scheduler-KPI/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Nick-Trigger/Harmony_Scheduler-KPI/actions/workflows/ci.yml)

## Architecture

### Folder Tree

```txt
backend/app/
├── api/                     # FastAPI route handlers
│   ├── errors.py               # Exception &rarr; HTTP response mapping
│   └── schedule.py             # POST /schedule
├── adapters/                # Client-specific I/O shapes
│   ├── base.py                 # Adapter protocol
│   └── client_a.py             # Client A request/response shape
├── domain/                  # Canonical, client-agnostic data model
│   ├── problem.py              # SchedulingProblem, Resource, Product, Operation
│   └── solution.py             # Solution, Assignment
├── solvers/                 # Constraint solvers
│   ├── _diagnostics.py         # Pre-solve infeasibility checks
│   ├── _op_vars.py             # Shared CP-SAT operation variables
│   ├── _time.py                # Minute-since-horizon helpers
│   ├── base.py                 # Solver protocol + InfeasibleError
│   └── cpsat.py                # OR-Tools CP-SAT implementation
├── objectives/              # Objective functions (registry-based)
│   ├── base.py                 # ObjectiveFn protocol + registry
│   └── min_tardiness.py        # The implemented objective
├── kpis.py                  # KPI calculation from canonical Solution
├── validation.py            # Post-solve invariant checks
└── main.py                  # FastAPI app composition

frontend/src/
├── App.tsx                  # Top-level component, state, layout
├── Gantt.tsx                # Inline SVG Gantt visualization
├── DataButton.tsx           # Upload JSON / load example controls
├── api.tsx                  # Backend client + TypeScript types
└── exampleData.tsx          # Default example payload
```

### Request flow

When `POST /schedule` is called, the request passes through these steps in order:

1. **Parse**: `adapters/{client}.py::parse_request` validates the JSON shape (via Pydantic) and translates it into the canonical `SchedulingProblem`.
2. **Diagnose**: `solvers/_diagnostics.py` runs pre-solve structural checks (missing capabilities, windows too short for any op, demand exceeding capacity, deadlines before the minimum achievable completion time). If any check fails, an `InfeasibleError` is raised with concrete reasons and the request short-circuits to a 422 response.
3. **Solve**: `solvers/cpsat.py::solve` builds the CP-SAT model (interval vars, no-overlap, precedence, calendars, changeovers, objective) and runs the solver. Returns a canonical `Solution`.
4. **Validate**: `validation.py::validate` independently re-checks the solution against every hard constraint. Catches solver bugs. Raises `InvariantError` on failure (mapped to a 500, representing a model failure).
5. **Compute KPIs**: `kpis.py::compute_kpis` derives tardiness, changeover count and minutes, makespan, and per-resource utilization from the canonical `Solution`.
6. **Format**: `adapters/{client}.py::format_response` translates the canonical `Solution` + KPIs back into Client's response shape and FastAPI returns it as the 200 body.

The solver, KPI calculator, and validator operate **only** on canonical domain types. Client-specific field names and shapes are confined to `adapters/`.

## Design notes

The system is designed around a strict separation between **canonical** types (client-agnostic, used by the solver, KPIs, and validation) and **adapter** types (client-specific JSON shapes). Every layer downstream of the adapter speaks the same vocabulary, regardless of which client sent the request.

This means almost any change including supporting a new client, adding an objective, adding a constraint, reshaping the response is a *localized* change affecting one or two files. The sections under [Making Changes](#making-changes) describe what touches what for each kind of change.

### Solver Choice & Approach

**Solver: OR-Tools CP-SAT.** Native support for interval variables, no-overlap
constraints, and optional intervals (used for resource assignment) made CP-SAT
a much better fit than a MIP or hand-rolled heuristic. For instances of the
size described in the spec, it solves in well under a second.

**Modeling strategy:**

- Each operation gets one optional interval per `(resource, working window)` pair, with conditional containment constraints enforced via `only_enforce_if`.
- Resource selection: `add_exactly_one` over per-resource presence booleans.
- No-overlap per resource via `add_no_overlap` on all intervals for that resource (across all windows).
- Family-dependent changeovers via the standard disjunctive pattern - one boolean per unordered pair selects the ordering, and the setup constraint for the chosen direction is enforced.
- Tardiness via `tardiness >= last_op.end - due`, lower-bounded at zero, summed and minimized.
- Determinism via `num_search_workers=1` and a fixed random seed.

**Pre-solve diagnostics.** For common infeasibility causes (missing capabilities,
windows too short, capacity below demand-plus-min-changeover-overhead, deadlines
before achievable completion), the system flags the issue *before* invoking
CP-SAT and surfaces actionable reasons. This addresses the spec's "concrete
reason" requirement and the bonus rubric's call for cleaner diagnostics.

### Making Changes

#### Adding a second client input/output format

##### Changing the input format

  When the goal is to accept a different JSON shape (e.g., Client B with renamed ERP fields or restructured arrays), the canonical model already represents what the solver actually needs. Only the translation layer changes.

  1. **Create a new adapter module** under `adapters/` (e.g., `client_b.py`) that implements the `Adapter` protocol from `adapters/base.py`. The two functions are `parse_request` (incoming JSON &rarr; canonical `SchedulingProblem`) and `format_response` (canonical `Solution` + KPIs &rarr; outgoing JSON).
  2. **Define Pydantic models** at the top of that adapter for Client B's request shape. Keep them module-private so nothing else in the codebase can import them.
  3. **Register a new route** under `api/` (typically a sibling to `schedule.py`, e.g. `schedule_client_b.py`) that uses the new adapter. The route handler runs the same pipeline as Client A: parse &rarr; solve &rarr; validate &rarr; KPIs &rarr; format (see [Request Flow](#request-flow)).
  4. **Wire the new router** into `main.py` via `app.include_router(...)`.

  What does *not* change: `domain/`, `solvers/`, `objectives/`, `kpis.py`,
  `validation.py`. If any of those need touching to accommodate Client B, the
  domain model is missing a concept and should be extended there instead.

##### Changing the response output format

The response shape is owned entirely by the adapter that produced it. Field names, nesting datetime formats, and computed metadata can all change without affecting anything else.

1. **Locate `format_response`** in the relevant adapter (eg: `adapters/client_a.py` for Client A).
2. **Modify the dict literal** that the function returns. Rename keys, restructure, add derived fields, change datetime formatting - whatever the new contract requires.
3. **Update the frontend's TypeScript types** in `frontend/src/api.tsx` to match the new response shape, if the frontend is the consumer.
4. **If the new format needs problem context** (e.g. emitting each product's family on each assignment), accept `problem: SchedulingProblem` as an extra parameter to `format_response` and pass it through from the API handler in `api/schedule.py`.

What does *not* change: `kpis.py`, `validation.py`, `solvers/`, or `domain/`. KPIs and validation work on the canonical `Solution`, not the wire format.

#### Adding a new objective

Objectives are managed by a registry (`objectives/base.py`) that maps a string name (used in `settings.objective_mode`) to a function that adds objective terms to the CP-SAT model. New objectives plug in without touching the solver.

1. **Create a new module** under `objectives/` (e.g., `max_throughput.py`).
2. **Implement `add_to_model(model, op_vars, problem)`**, which is a function that adds the relevant decision variables and calls `model.minimize(...)` or `model.maximize(...)`.
3. **Register it at module load** with `register("max_throughput", add_to_model)` at the bottom of the file.
4. **Import the new module** in `objectives/__init__.py` so registration runs on app startup.

The API automatically accepts the new objective name in `settings.objective_mode` and returns a 400 for unknown values.

#### Adding a new constraint

A new constraint usually means a new property on the problem (a maintenance window, a frozen zone, a precedence between two products). The domain model captures it, the adapter parses it, the solver enforces it, and validation verifies it.

1. **Extend the canonical model** in `domain/problem.py` with the new field. Use frozen dataclasses with appropriate types (`tuple`, `frozenset`, etc. - anything hashable).
2. **Parse the new field** in each affected adapter's `parse_request`. Add the corresponding Pydantic input model fields.
3. **Enforce the constraint** in `solvers/cpsat.py`. New constraints generally take the form of additional `model.add(...)` calls, often gated by `only_enforce_if(...)` for conditional logic.
4. **Verify the constraint** in `validation.py`. Add a `_check_*` function that walks the solution and raises `InvariantError` if the constraint is violated. Wire it into the `validate()` orchestrator.
5. **Add a pre-solve diagnostic** in `solvers/_diagnostics.py` if there's a structural way to detect infeasibility before invoking the solver. Optional, but improves error messages.

The pattern: **domain defines, adapter parses, solver enforces, validation verifies.**

#### Changing error response shapes

HTTP status codes and error response bodies are mapped centrally in `api/errors.py` via FastAPI exception handlers. Different exceptions become different responses, but the exception-raising code never has to know about HTTP.

1. **Locate the handler** in `api/errors.py` for the exception type you want to change (`InfeasibleError`, `InvariantError`, `ValueError`, or FastAPI's `RequestValidationError`).
2. **Update the `JSONResponse`** body or status code in that handler.
3. **For a new exception type entirely**, define it in the module that raises it, then add a handler in `api/errors.py` and register it via `register_handlers(app)`.

> The layer that raises the exception doesn't need to know what HTTP status it produces.

### Assumptions and tradeoffs

- **Single solver per request.** No async queueing or job IDs. For the spec's problem size this is fine; production would want background scheduling.
- **All timestamps are local site time.** Per spec - no timezone handling.
- **Tardiness as the only objective.** The codebase is structured for more (registry pattern, protocol-based), but only `min_tardiness` is shipped.
- **No persistence.** Problems aren't saved; results aren't cached. Each request is independent.
- **Pre-solve diagnostics are a lower bound.** Some infeasibility only emerges from solver-discovered interactions - these surface as a generic "constraints are mutually unsatisfiable" message rather than a specific reason. The alternative (CP-SAT's `sufficient_assumptions_for_infeasibility`) would require restructuring the model and was deferred.
- **Output sorted for determinism.** Assignments are sorted by `(start, product, step)` so repeated runs produce byte-identical output, satisfying the spec's determinism acceptance check.

## API documentation

With the backend running:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Raw OpenAPI schema: <http://localhost:8000/openapi.json>

> Note: These auto-generated API references will show Input/Output response shapes currently loaded by the backend. See [Design Notes](#design-notes) for information.

### Endpoints

| Method | Path        | Description                                              |
|--|-|-|
| `POST` | `/schedule` | Solve a scheduling problem and return assignments + KPIs |
| `GET`  | `/health`   | Liveness probe - returns `{"status": "ok"}`              |

#### `POST /schedule`

The request body schema is defined in the backend adapter that owns the wire format. For Client A, see [`backend/app/adapters/ReadMe_client_a.md`](backend/app/adapters/ReadMe_client_a.md) for the full field-by-field reference.

##### Response - 200 (feasible)

```json
{
  "assignments": [
    {
      "product": "P-100",
      "step_index": 1,
      "capability": "fill",
      "resource": "Fill-2",
      "start": "YYYY-MM-DDTHH:MM:SS",
      "end": "YYYY-MM-DDTHH:MM:SS"
    },
    ...
  ],
  "kpis": {
    "tardiness_minutes": int, 
    "changeover_count": int,
    "changeover_minutes": int,
    "makespan_minutes": int,
    "utilization_pct": {
      "Fill-1": int,  //pct
      "Fill-2": int,  //pct
      "Label-1": int, //pct
      "Pack-1": int   //pct
    }
  }
}

```

Assignment fields:

- `product`: references a `products[].id` from the request
- `step_index`: 1-based, matches the position in that product's `route`
- `capability`: copy of the route's capability for that step
- `resource`: references a `resources[].id`
- `start` / `end`: when the operation runs

KPI fields:

- `tardiness_minutes`: total minutes late across all products (`sum of max(0, completion - due)`)
- `changeover_count`: number of consecutive same-resource ops that crossed family boundaries
- `changeover_minutes`: total setup minutes inserted for those changeovers
- `makespan_minutes`: latest assignment end minus earliest assignment start
- `utilization_pct[resource_id]`: processing minutes / horizon-clipped calendar minutes × 100 rounded. Changeover minutes are excluded from the numerator.

##### Response - 422 (infeasible)

Returned when the problem cannot be solved within the constraints. Distinguished from validation errors (which use the same status code) by the response shape.

```json
{
  "error": "infeasible",
  "why": [
    "'fill' capacity insufficient even with optimistic ordering: 335 min of work + at least 30 min of family changeovers required, but only 360 min available (1 machine(s), 2 family(ies))",
    ...
  ]
}
```

The `why` field contains at least one concrete, actionable reason. Common causes:

- A capability is required but no resource provides it
- A working window is shorter than any operation that would run in it
- Total processing demand for a capability exceeds available capacity
- A product's deadline is earlier than its minimum possible completion time
- Solver reports no feasible solution exists (structural checks all passed)

##### Response - 400 (bad request)

Returned for unknown `objective_mode` and other client-side input errors:

```json
{
  "error": "bad_request",
  "detail": "unknown objective_mode 'foo'; available: min_tardiness"
}
```

Pydantic-level shape errors (missing required fields, wrong types) come through FastAPI's default 422 `HTTPValidationError` with a `detail` array pinpointing the offending field path.

#### `GET /health`

Simple liveness probe:

```json
{ "status": "ok" }
```

Useful for monitoring and container orchestration health checks.

### Using the API

`POST /schedule` accepts a scheduling problem and returns either:

- **200** - a feasible schedule with KPIs, or
- **422** - a structured infeasibility response with concrete reasons, or
- **400** - a bad request (e.g., unknown `objective_mode`)

#### Example via the frontend

Open [http://localhost:5173] and click **Schedule example** to run the spec's
example input. Use the **Upload JSON** button to send a custom payload.

Three sample inputs live under [`backend/tests/example_data/`](/backend/tests/example_data/):

- `example_a.json`: the spec's reference example
- `complex_a.json`: a larger 15-product fixture across 4 families
- `force_tardy.json`: a stress case that genuinely cannot finish on time

#### Example via curl

**macOS / Linux:**

```bash
curl -X POST http://localhost:8000/schedule \
  -H "Content-Type: application/json" \
  -d @backend/tests/example_data/example_a.json
```

**Windows (PowerShell):**

```powershell
curl.exe -X POST http://localhost:8000/schedule `
  -H "Content-Type: application/json" `
  -d "@backend/tests/example_data/example_a.json"
```

> Note: Windows PowerShell aliases `curl` to `Invoke-WebRequest`, which has different syntax. Use `curl.exe` to invoke the real curl binary (shipped with Windows 10+).

Pipe the response through a JSON formatter to make it readable:

**macOS / Linux** (with `jq`):

```bash
curl -s -X POST http://localhost:8000/schedule \
  -H "Content-Type: application/json" \
  -d @backend/tests/example_data/example_a.json | jq
```

**Windows (PowerShell)** (built-in formatting):

```powershell
curl.exe -s -X POST http://localhost:8000/schedule `
  -H "Content-Type: application/json" `
  -d "@backend/tests/example_data/example_a.json" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

#### Example via interactive docs

FastAPI auto-generates Swagger UI at <http://localhost:8000/docs>. Paste any input and execute it from the browser.

> Note: This auto-generated API reference will show Input/Output response shapes currently loaded by the backend. See [Design Notes](#design-notes) for information.
