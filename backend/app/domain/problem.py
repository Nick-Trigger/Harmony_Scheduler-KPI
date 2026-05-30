from dataclasses import dataclass
from datetime import datetime

# Types: Str not Enum to allow for dynamic capabilities (eg: different capabilities per client)

Capability = str
Family = str


@dataclass(frozen=True)
class Horizon:
    "Time Window for the problem"

    start: datetime
    end: datetime


@dataclass(frozen=True)
class WorkingWindow:
    "Continuous window in which a resource is available"

    start: datetime
    end: datetime


@dataclass(frozen=True)
class Resource:
    "Resource that can be assigned to a task (eg: machine, stationn, worker...)"

    id: str
    capabilities: frozenset[Capability]
    working_windows: tuple[WorkingWindow, ...]


@dataclass(frozen=True)
class Operation:
    "A single step in product's route"

    capability: Capability
    duration_minutes: int


@dataclass(frozen=True)
class Product:
    "Product to be manufactured"

    id: str
    family: Family
    due: datetime
    route: tuple[Operation, ...]


@dataclass(frozen=True)
class ChangeoverMatrix:
    "Changeover time between two operations"

    values: dict[tuple[Family, Family], int]  # in minutes

    def setup_minutes(self, from_family: Family, to_family: Family) -> int:
        "Get the setup time in minutes between two families"
        if from_family == to_family:
            return 0  # no setup time if same family
        return self.values.get((from_family, to_family), 0)


@dataclass(frozen=True)
class SolverSettings:
    "Settings for the solver"

    time_limit_seconds: int
    objective_mode: str


@dataclass(frozen=True)
class SchedulingProblem:
    "The scheduling problem to be solved"

    horizon: Horizon
    resources: tuple[Resource, ...]
    products: tuple[Product, ...]
    changeover_matrix: ChangeoverMatrix
    settings: SolverSettings
