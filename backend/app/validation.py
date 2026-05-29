"""
Validates CP-SAT solutions.

Checks for two things overall:
1) Invariants that must hold for any valid solution.
2) Constraints that must be satisfied.
"""


from datetime import timedelta

from app.domain.problem import SchedulingProblem
from app.domain.solution import Assignment, Solution

class InvariantError(Exception):
    """Raised when a Solution violates a hard constraint.

    Distinct from InfeasibleError: this means the solver produced an invalid output, not that no solution exists.
    """

    def __init__(self, message: str):
        super().__init__(message)
        
        
# %% Elegibility

def _check_elegibility(problem: SchedulingProblem, solution: Solution) -> None:
    "Every assignment runs on a resource that has the required capability."
    
    resources_by_id = {r.id: r for r in problem.resources}
    for a in solution.assignments:
        resource = resources_by_id.get(a.resource_id)
        if resource is None:
            raise InvariantError(
                f"Assignment for {a.product_id} step {a.step_index} is not eligible, references unknown resource {a.resource_id!r}"
                ) # Assignment for P-100 step 0 is not eligible, references unknown resource 'Fill-1'
        
        if a.capability not in resource.capabilities:
            raise InvariantError(
                f"Assignment for {a.product_id} step {a.step_index} is not eligible, resource {a.resource_id!r} lacks capability {a.capability!r}"
                ) # Assignment for P-100 step 0 is not eligible, resource 'Fill-1' lacks capability 'Label'
        
# %% No Overlap

def _check_no_overlap(solution: Solution) -> None:
    "Checks that no two assignments overlap in time on the same resource."
    
    by_resource: dict[str, list[Assignment]] = {}
    for a in solution.assignments:
        by_resource.setdefault(a.resource_id, []).append(a)

    for resource_id, assignments in by_resource.items():
        assignments.sort(key=lambda a: a.start)
        for prev, curr in zip(assignments, assignments[1:]):
            if curr.start < prev.end:
                raise InvariantError(
                    f"overlap on {resource_id}: {prev.product_id} step {prev.step_index} ({prev.start.isoformat()}-{prev.end.isoformat()}) overlaps {curr.product_id} step {curr.step_index} ({curr.start.isoformat()}-{curr.end.isoformat()})"
                ) # overlap on Fill-1: P-100 step 0 (2025-11-03T08:00:00–2025-11-03T08:30:00) overlaps P-101 step 0 (2025-11-03T08:15:00–2025-11-03T08:45:00)
                
# %% Precedence

def _check_precedence(problem: SchedulingProblem, solution: Solution) -> None:
    "Checks that each product's assignments are in the correct order."
    
    by_product: dict[str, list[Assignment]] = {}
    for a in solution.assignments:
        by_product.setdefault(a.product_id, []).append(a)

    for product_id, assignments in by_product.items():
        assignments.sort(key=lambda a: a.step_index)
        for prev, curr in zip(assignments, assignments[1:]):
            if curr.start < prev.end:
                raise InvariantError(
                    f"precedence violation for {product_id}: step {prev.step_index} ({prev.start.isoformat()}-{prev.end.isoformat()}) precedes step {curr.step_index} ({curr.start.isoformat()}-{curr.end.isoformat()})"
                ) # precedence violation for P-100: step 0 (2025-11-03T08:00:00–2025-11-03T08:30:00) precedes step 1 (2025-11-03T08:15:00–2025-11-03T08:35:00)
                
# %% Working Windows

def _check_working_windows(problem: SchedulingProblem, solution: Solution) -> None:
    "Checks that each assignment is within the resource's working windows."
    
    resources_by_id = {r.id: r for r in problem.resources}
    for a in solution.assignments:
        resource = resources_by_id.get(a.resource_id)
        if resource is None:
            raise InvariantError(
                f"Assignment for {a.product_id} step {a.step_index} references unknown resource {a.resource_id!r}"
            )
        
        # Check if assignment is within any of the working windows
        if not any(window.start <= a.start and a.end <= window.end for window in resource.working_windows):
            raise InvariantError(
                f"Assignment for {a.product_id} step {a.step_index} on resource {a.resource_id!r} ({a.start.isoformat()}-{a.end.isoformat()}) is outside of working windows"
            ) # Assignment for P-100 step 0 on resource 'Fill-1' (2025-11-03T08:00:00-2025-11-03T08:30:00) is outside of working windows
            
# %% Changeovers

def _check_changeovers(problem: SchedulingProblem, solution: Solution) -> None:
    "When consecutive ops on the same resource differ in family, checks that the changeover duration is respected."
    
    family_by_product = {p.id: p.family for p in problem.products}
    matrix = problem.changeover_matrix
    
    by_resource: dict[str, list[Assignment]] = {}
    for a in solution.assignments:
        by_resource.setdefault(a.resource_id, []).append(a)
        
    for resource_id, assignments in by_resource.items():
        assignments.sort(key=lambda a: a.start)
        for prev, curr in zip(assignments, assignments[1:]):
            setup = matrix.setup_minutes(
                family_by_product[prev.product_id],
                family_by_product[curr.product_id],
            )
            if setup == 0:
                continue
            actual_gap = curr.start - prev.end
            required = timedelta(minutes=setup)
            if actual_gap < required:
                raise InvariantError(
                    f"changeover violation on {resource_id}: {prev.product_id}->{curr.product_id} needs {setup} min setup but only {int(actual_gap.total_seconds() / 60)} min between {prev.end.isoformat()} and {curr.start.isoformat()}"
                ) # changeover violation on Fill-1: P-100->P-101 needs 30 min setup but only 15 min between 2025-11-03T08:30:00 and 2025-11-03T08:45:00
                
# %% Horizon

def _check_horizon(problem: SchedulingProblem, solution: Solution) -> None:
    "Checks that all assignments are within the problem's horizon."
    
    for a in solution.assignments:
        if a.start < problem.horizon.start or a.end > problem.horizon.end:
            raise InvariantError(
                f"Assignment for {a.product_id} step {a.step_index} ({a.start.isoformat()}-{a.end.isoformat()}) is outside of horizon ({problem.horizon.start.isoformat()}-{problem.horizon.end.isoformat()})"
            ) # Assignment for P-100 step 0 (2025-11-03T08:00:00-2025-11-03T08:30:00) is outside of horizon (2025-11-03T08:00:00-2025-11-03T16:00:00)
            

# %% General

def _check_assignment(problem: SchedulingProblem, solution: Solution) -> None:
    """
    Checks that all assignments are valid:
    
    1) Checks that each assignment references a valid product
    2) Checks that each assignment references a valid route operation
    3) Checks that each assignment's duration matches the route operation's duration
    """
    
    products_by_id = {p.id: p for p in problem.products}
    for a in solution.assignments:
        product = products_by_id.get(a.product_id)
        if product is None:
            raise InvariantError(
                f"Assignment for {a.product_id} step {a.step_index} references unknown product {a.product_id!r}"
            )
            
        step_idx_zero = a.step_index - 1
        if not (0 <= step_idx_zero < len(product.route)):
            raise InvariantError(
                f"step_index {a.step_index} out of range for {a.product_id} "
                f"(route has {len(product.route)} steps)"
            )
            
        expected = product.route[step_idx_zero].duration_minutes
        actual = int((a.end - a.start).total_seconds() / 60)
        if actual != expected:
            raise InvariantError(
                f"duration mismatch for {a.product_id} step {a.step_index}: "
                f"route says {expected} min, assignment has {actual} min"
            )
            
            
def validate(problem: SchedulingProblem, solution: Solution) -> None:
    "Run all validation checks. Raises InvariantError if any check fails."
    
    _check_elegibility(problem, solution)
    _check_no_overlap(solution)
    _check_precedence(problem, solution)
    _check_working_windows(problem, solution)
    _check_changeovers(problem, solution)
    _check_horizon(problem, solution)
    _check_assignment(problem, solution)