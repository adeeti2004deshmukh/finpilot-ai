from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_endpoint_contains_expected_summary() -> None:
    response = client.get("/api/v1/demo")
    assert response.status_code == 200
    assert response.json()["profile_name"] == "Aarav Mehta"
    assert response.json()["summary"]["financial_health_score"] == 87


def test_summary_endpoint_rejects_negative_values() -> None:
    response = client.post(
        "/api/v1/summary",
        json={
            "monthly_take_home_income": -1,
            "essential_expenses": 100,
            "discretionary_expenses": 0,
        },
    )
    assert response.status_code == 422


def test_simulation_endpoints() -> None:
    sip = client.post(
        "/api/v1/simulations/sip",
        json={"monthly_contribution": 1000, "annual_rate_percent": 0, "months": 12},
    )
    fd = client.post(
        "/api/v1/simulations/fd",
        json={"principal": 100000, "annual_rate_percent": 0, "months": 12},
    )
    assert sip.status_code == 200
    assert sip.json()["maturity_value"] == "12000.00"
    assert fd.status_code == 200
    assert fd.json()["maturity_value"] == "100000.00"