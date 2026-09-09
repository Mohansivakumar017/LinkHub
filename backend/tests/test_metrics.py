from fastapi.testclient import TestClient

from app.core.metrics import route_label
from app.main import app


def test_metrics_endpoint_exposes_prometheus_metrics() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")
    assert response.status_code == 200

    metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200
    assert "linkhub_http_requests_total" in metrics_response.text
    assert 'method="GET"' in metrics_response.text
    assert 'path="/api/v1/health"' in metrics_response.text
    assert "linkhub_url_cache_hits_total" in metrics_response.text
    assert "linkhub_url_cache_misses_total" in metrics_response.text


def test_route_label_does_not_use_unmatched_user_paths() -> None:
    assert route_label("/api/v1/urls/user-controlled-value", None) == "<unmatched>"
