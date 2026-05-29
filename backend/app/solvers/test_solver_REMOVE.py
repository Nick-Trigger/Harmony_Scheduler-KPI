# from backend:
# uv run python -m app.solvers.test_solver_REMOVE

import json
from typing import Any

from app.adapters.client_a import parse_request, format_response
from app.solvers.cpsat import solve
from app.validation import validate
from app.kpis import compute_kpis

def RunSolver(data: Any, verbose: bool =False):
    problem = parse_request(data)
    solution = solve(problem)
    kpis = compute_kpis(problem, solution)
    if verbose:
        print(json.dumps(format_response(solution, kpis=kpis), indent=2))
        print("-" * 50)
    validate(problem, solution)
    
    return solution

if __name__ == "__main__":
    with open("..\\.data\\example.json") as f:
        data = json.load(f)
    
    RunSolver(data, True)