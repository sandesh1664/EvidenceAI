from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["service"] == "EvidenceAI API"
    assert response.json()["status"] == "healthy"
    assert response.json()["version"] == "1.0.0"
