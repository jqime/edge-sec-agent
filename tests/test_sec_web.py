import os
import subprocess
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


from src.sec_web import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _stable_dependencies():
    with (
        patch("src.sec_web._check_ollama", return_value={"ok": True, "latency_ms": 1.0}),
        patch("src.sec_web._check_sqlite", return_value={"ok": True, "detail": "ok", "latency_ms": 1.0}),
        patch("src.sec_web._last_update_info", return_value={"updated_at": None, "commit": "abc", "channel": "stable"}),
    ):
        yield


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


# ── Chat path tests ────────────────────────────────────────────────────────

def _assert_real_script(args):
    """Comprueba que el primer argumento es la ruta real y ejecutable de sec-agent."""
    script = args[0]
    assert script != "_SECURE_AGENT_SCRIPT", "se está usando el literal en vez de la variable"
    assert os.path.isabs(script), f"la ruta no es absoluta: {script}"
    assert not script.startswith("/root"), f"la ruta apunta a /root: {script}"
    assert os.path.basename(script) == "sec-agent", f"basename inesperado: {script}"
    assert os.path.exists(script), f"la ruta no existe: {script}"
    assert os.access(script, os.X_OK), f"la ruta no es ejecutable: {script}"


class TestChatPaths:
    @patch("subprocess.run")
    def test_chat_uses_real_script_path(self, mock_run, client):
        """El endpoint debe usar la ruta real y ejecutable de sec-agent (no un literal)."""
        mock_run.return_value.stdout = "informe"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0

        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "estado"}]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["choices"][0]["message"]["content"] == "informe"
        assert mock_run.called
        args = mock_run.call_args[0][0]
        _assert_real_script(args)
        assert "--security" in args, "falta el flag --security"

    @patch("subprocess.run")
    def test_ask_uses_real_script_path(self, mock_run, client):
        """El endpoint /ask debe usar la ruta real de sec-agent con --security."""
        mock_run.return_value.stdout = "informe"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0

        resp = client.post("/ask", json={"pregunta": "estado"})
        assert resp.status_code == 200
        assert resp.get_json()["respuesta"] == "informe"
        assert mock_run.called
        args = mock_run.call_args[0][0]
        _assert_real_script(args)
        assert "--security" in args, "falta el flag --security"

    @patch("subprocess.run")
    def test_chat_exception_returns_error_spanish(self, mock_run, client):
        """Con subprocess.run lanzando excepción, respuesta contiene 'Error ejecutando sec-agent'."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "sec-agent")
        response = client.post(
            "/v1/chat/completions",
            json={"model": "tinyllama:1.1b", "prompt": "OK", "stream": False},
        )
        data = response.get_json()
        assert "Error ejecutando sec-agent" in data["choices"][0]["message"]["content"]

    @patch("subprocess.run")
    def test_ask_exception_returns_error_spanish(self, mock_run, client):
        """Con subprocess.run lanzando excepción en /ask, respuesta contiene error."""
        mock_run.side_effect = subprocess.TimeoutExpired("sec-agent", 30)
        response = client.post("/ask", json={"pregunta": "estado"})
        data = response.get_json()
        assert "Error ejecutando sec-agent" in data["respuesta"]


@pytest.mark.integration
def test_chat_integration_runs_real_agent(client, tmp_path, monkeypatch):
    """Integración: ejecuta el endpoint real (sin mock) y valida informe no vacío.

    Se marca como 'integration' porque lanza el binario sec-agent real (lento) y
    escribe en una BD y un directorio de informes temporales, no en producción.
    """
    monkeypatch.setenv("EDGE_DB_PATH", str(tmp_path / "integration.db"))
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "reports"))
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "estado"}]},
    )
    assert resp.status_code == 200
    content = resp.get_json()["choices"][0]["message"]["content"]
    assert content.strip() != "", "el endpoint devolvió contenido vacío"
    assert content != "Error ejecutando sec-agent"
    assert "[ERROR]" not in content


# ── Bootstrap validation ──────────────────────────────────────────────────

def test_bootstrap_no_ls_route():
    """Comprueba que el script bootstrap no usa 'git ls-route' (comando inexistente)."""
    with open("scripts/bootstrap_debian_arm64.sh", "r") as f:
        content = f.read()
    assert "git ls-route" not in content, (
        "bootstrap_debian_arm64.sh usa 'git ls-route', comando que no existe"
    )