# Backend

A scheduling service that accepts a production scheduling problem as JSON and
returns a feasible schedule plus KPIs. Built with FastAPI and OR-Tools CP-SAT.

## Architecture

```txt
backend/app/
├── api/                     # FastAPI route handlers (thin — no business logic)
│   └── schedule.py             # POST /schedule
├── adapters/                # Client-specific I/O (JSON to canonical model)
│   ├── base.py                 # Adapter protocol
│   └── client_a.py             # Client A request/response shape
├── domain/                  # Canonical, client-agnostic data model
│   ├── problem.py              # SchedulingProblem, Resource, Product, Operation
│   └── solution.py             # Solution, Assignment
├── solvers/                 # Constraint solvers
│   ├── base.py                 # Solver protocol
│   ├── cpsat.py                # OR-Tools CP-SAT implementation
│   └── _{globalHelpers}.py
├── objectives/              # Objective functions (e.g. min_tardiness)
│   ├── base.py                 # Objective protocol
│   └── min_tardiness.py        
├── kpis.py                  # KPI calculation from a canonical Solution
└── validation.py            # Invariant checks (overlap, precedence, calendars)
```

## Request flow

```txt
JSON request
→ adapters/client_a.py      (parse → canonical SchedulingProblem)
→ solvers/cpsat.py          (solve → canonical Solution)
→ validation.py             (sanity-check invariants)
→ kpis.py                   (compute KPIs)
→ adapters/client_a.py      (canonical → JSON response)
JSON response
```

## Design principle

The solver, KPI calculator, and validator operate **only** on canonical domain
types. Client-specific field names and shapes live exclusively in `adapters/`.
This keeps the core scheduling logic stable as new client formats are added.
