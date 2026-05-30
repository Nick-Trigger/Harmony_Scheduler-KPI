from datetime import datetime, timedelta

def to_minutes(t: datetime, origin: datetime) -> int:
    "Convert a datetime to int minutes since `origin`."
    delta = t - origin
    # Round to nearest minute.
    return int(delta.total_seconds() // 60)

def from_minutes(m: int, origin: datetime) -> datetime:
    "Convert integer minutes since `origin` back to a datetime."
    return origin + timedelta(minutes=m)