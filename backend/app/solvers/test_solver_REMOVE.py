# from backend:
# uv run python -m app.solvers.test_solver_REMOVE

from app.adapters.client_a import parse_request, format_response
from app.solvers.cpsat import solve
import json

# simple = {
#   'horizon': {'start': '2025-11-03T08:00:00', 'end': '2025-11-03T16:00:00'},
#   'resources': [
#     {'id': 'Fill-1', 'capabilities': ['fill'],
#      'calendar': [['2025-11-03T08:00:00', '2025-11-03T16:00:00']]},
#     {'id': 'Label-1', 'capabilities': ['label'],
#      'calendar': [['2025-11-03T08:00:00', '2025-11-03T16:00:00']]}
#   ],
#   'products': [
#     {'id': 'P-100', 'family': 'standard', 'due': '2025-11-03T12:30:00',
#      'route': [
#        {'capability': 'fill', 'duration_minutes': 30},
#        {'capability': 'label', 'duration_minutes': 20}
#      ]}
#   ],
#   'changeover_matrix_minutes': {'values': {
#     'standard->standard': 0, 'standard->premium': 20,
#     'premium->standard': 20, 'premium->premium': 0}},
#   'settings': {'time_limit_seconds': 5, 'objective_mode': 'min_tardiness'}
# }

with open("..\\.data\\example.json") as f:
    simple = json.load(f)

problem = parse_request(simple)
solution = solve(problem)
print(json.dumps(format_response(solution, kpis={}), indent=2))
