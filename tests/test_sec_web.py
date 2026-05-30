import os
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_db():
    tmp = tempfile.mktemp(suffix=".db")
    os.environ["EDGE_DB_PATH"] = tmp
    yield
    os.environ.pop("EDGE_DB_PATH", None)
    try:
        os.remove(tmp)
    except OSError:
        pass


from src.sec_web import app  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── /v1/global/health ────────────────────────────────────────────────────

class TestHealth:
    @patch("src.sec_web._get_cpu_temp", return_value=45.0)
    @patch("src.sec_web._get_ram_percent", return_value=50.0)
    @patch("src.sec_web._get_uptime_seconds", return_value=3600.0)
    @patch("src.sec_web._get_fail2ban_banned_ips", return_value=3)
    @patch("src.sec_web.get_latest", return_value={"score": 85})
    def test_healthy(self, mock_latest, mock_banned, mock_uptime, mock_ram, mock_temp, client):
        resp = client.get("/v1/global/health")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["status"] == "HEALTHY"
        assert data["security_score"] == 85
        assert data["fail2ban_banned_ips"] == 3
        assert data["uptime_seconds"] == 3600.0
        assert data["hardware"]["cpu_temp_c"] == 45.0
        assert data["hardware"]["ram_percent"] == 50.0
        assert data["warnings"] == []

    @patch("src.sec_web._get_cpu_temp", return_value=72.0)
    @patch("src.sec_web._get_ram_percent", return_value=50.0)
    @patch("src.sec_web._get_uptime_seconds", return_value=0.0)
    @patch("src.sec_web._get_fail2ban_banned_ips", return_value=0)
    @patch("src.sec_web.get_latest", return_value=None)
    def test_degraded_high_temp(self, mock_latest, mock_banned, mock_uptime, mock_ram, mock_temp, client):
        resp = client.get("/v1/global/health")
        data = resp.get_json()
        assert resp.status_code == 503
        assert data["status"] == "DEGRADED"
        assert "Temperatura crítica" in data["warnings"][0]

    @patch("src.sec_web._get_cpu_temp", return_value=60.0)
    @patch("src.sec_web._get_ram_percent", return_value=92.0)
    @patch("src.sec_web._get_uptime_seconds", return_value=0.0)
    @patch("src.sec_web._get_fail2ban_banned_ips", return_value=0)
    @patch("src.sec_web.get_latest", return_value=None)
    def test_degraded_high_ram(self, mock_latest, mock_banned, mock_uptime, mock_ram, mock_temp, client):
        resp = client.get("/v1/global/health")
        data = resp.get_json()
        assert resp.status_code == 503
        assert data["status"] == "DEGRADED"
        assert any("RAM crítica" in w for w in data["warnings"])

    @patch("src.sec_web._get_cpu_temp", return_value=60.0)
    @patch("src.sec_web._get_ram_percent", return_value=80.0)
    @patch("src.sec_web._get_uptime_seconds", return_value=0.0)
    @patch("src.sec_web._get_fail2ban_banned_ips", return_value=0)
    @patch("src.sec_web.get_latest", return_value=None)
    def test_warnings_not_degraded(self, mock_latest, mock_banned, mock_uptime, mock_ram, mock_temp, client):
        resp = client.get("/v1/global/health")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["status"] == "HEALTHY"
        assert len(data["warnings"]) == 2
        assert any("Temperatura elevada" in w for w in data["warnings"])
        assert any("RAM elevada" in w for w in data["warnings"])

    def test_returns_json(self, client):
        """Verifica que Content-Type sea application/json incluso sin mocks."""
        resp = client.get("/v1/global/health")
        assert resp.content_type == "application/json"
        assert "status" in resp.get_json()


# ── /metrics ─────────────────────────────────────────────────────────────

class TestMetrics:
    @patch("src.sec_web._get_cpu_temp", return_value=50.0)
    @patch("src.sec_web._get_ram_percent", return_value=40.0)
    @patch("src.sec_web._get_fail2ban_banned_ips", return_value=2)
    @patch("src.sec_web.get_latest", return_value={"score": 90})
    def test_prometheus_format(self, mock_latest, mock_banned, mock_ram, mock_temp, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.content_type
        body = resp.get_data(as_text=True)
        assert "edge_sec_cpu_temperature_celsius 50.0" in body
        assert "edge_sec_ram_used_percentage 40.0" in body
        assert "edge_sec_security_score 90" in body
        assert "edge_sec_fail2ban_banned_ips 2" in body


# ── /api/metrics ─────────────────────────────────────────────────────────

class TestApiMetrics:
    @patch("src.sec_web._count_ssh_failures", return_value=5)
    @patch("src.sec_web._get_open_ports", return_value=["8080"])
    @patch("src.sec_web._get_temperature_c", return_value=55.0)
    @patch("src.sec_web._get_ram_usage_percent", return_value=70.0)
    @patch("src.sec_web._compute_score", return_value=85)
    def test_returns_full_metrics(self, mock_score, mock_ram, mock_temp, mock_ports, mock_ssh, client):
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "score" in data
        assert data["score"] == 85
        assert data["ssh_failures"] == 5
        assert "8080" in data["open_ports"]
        assert data["temp_c"] == 55.0
        assert data["ram_percent"] == 70.0


# ── /v1/models ───────────────────────────────────────────────────────────

class TestModels:
    def test_list_models(self, client):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "sec-agent"


# ── / and dashboard ──────────────────────────────────────────────────────

class TestIndex:
    def test_dashboard_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.content_type == "text/html; charset=utf-8"
        body = resp.get_data(as_text=True)
        assert "Edge Sec Agent Dashboard" in body
        assert "/api/metrics" in body
        assert "/v1/global/health" in body
        assert "/metrics" in body
        assert "/v1/models" in body
