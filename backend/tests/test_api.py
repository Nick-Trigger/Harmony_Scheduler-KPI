from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_post_schedule_happy_path(example_a_payload):
    "Spec example produces a 200 with assignments and KPIs."
    response = client.post("/schedule", json=example_a_payload)
    assert response.status_code == 200
    body = response.json()
    assert "assignments" in body
    assert "kpis" in body
    assert body["kpis"]["tardiness_minutes"] >= 0


def test_post_schedule_infeasible_returns_422_with_reasons(example_a_payload):
    "Tightening the horizon to 30 minutes makes the problem infeasible."
    payload = dict(example_a_payload)
    payload["horizon"] = {
        "start": "2025-11-03T08:00:00",
        "end": "2025-11-03T08:30:00",
    }

    response = client.post("/schedule", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "infeasible"
    assert isinstance(body["why"], list)
    assert (len(body["why"]) >= 1) and (any(reason != "solver reports the model is infeasible but no specific reasons were found" for reason in body["why"]))   # spec: "at least one concrete reason"


def test_post_schedule_unknown_objective_returns_400(example_a_payload):
    "Bad objective_mode is a client error, not infeasibility."
    payload = dict(example_a_payload)
    payload["settings"] = dict(payload["settings"])
    payload["settings"]["objective_mode"] = "nonexistent_mode"

    response = client.post("/schedule", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert "nonexistent_mode" in body["detail"]