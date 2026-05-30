from dataclasses import dataclass

from ortools.sat.python import cp_model

@dataclass
class OpVars:
    "CP-SAT variables for one operation in one product's route."

    product_id: str
    step_index: int  # 1-based to match wire format
    capability: str
    family: str
    duration: int

    start: cp_model.IntVar  # minutes since horizon start
    end: cp_model.IntVar

    # One optional interval per eligible resource. Exactly one is present.
    presences: dict[tuple[str, int], cp_model.IntVar]
    intervals: dict[tuple[str, int], cp_model.IntervalVar]