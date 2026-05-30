import os
import tempfile
from unittest.mock import mock_open, patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_db():
    """Usa BD temporal para evitar efectos secundarios en import de agent.py."""
    tmp = tempfile.mktemp(suffix=".db")
    os.environ["EDGE_DB_PATH"] = tmp
    yield
    os.environ.pop("EDGE_DB_PATH", None)
    try:
        os.remove(tmp)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _clean_env():
    """Limpia variables que agent.py lee al cargar."""
    for k in ("SSH_LOG_PATHS", "EDGE_MODEL", "EDGE_MAX_TOKENS", "EDGE_TIMEOUT", "REPORTS_DIR"):
        os.environ.pop(k, None)
    yield


# Importar agent DESPUÉS de los fixtures de entorno
import src.agent as agent  # noqa: E402


# ── _compute_score ────────────────────────────────────────────────────────

class TestComputeScore:
    def test_max_score_no_issues(self):
        assert agent._compute_score(0, [], None, None) == 100

    def test_ssh_failures_penalty(self):
        assert agent._compute_score(5, [], None, None) == 90   # 5*2=10
        assert agent._compute_score(30, [], None, None) == 40   # 30*2=60
        assert agent._compute_score(50, [], None, None) == 40   # capped at 60

    def test_risk_ports_penalty(self):
        assert agent._compute_score(0, ["8080"], None, None) == 92   # 1*8=8
        assert agent._compute_score(0, ["8080", "3306", "21", "23", "111"], None, None) == 60  # 5*8=40 capped

    def test_allowed_ports_no_penalty(self):
        assert agent._compute_score(0, ["22", "80", "443", "25", "53"], None, None) == 100

    def test_temperature_penalty(self):
        assert agent._compute_score(0, [], 60.0, None) == 93   # (60-55)*1.5=7.5→int=7, 100-7=93
        assert agent._compute_score(0, [], 80.0, None) == 75   # (80-55)*1.5=37.5→25 capped

    def test_ram_penalty(self):
        assert agent._compute_score(0, [], None, 70.0) == 92   # (70-60)*0.8=8
        assert agent._compute_score(0, [], None, 95.0) == 75   # capped at 25

    def test_combined_penalties(self):
        score = agent._compute_score(10, ["8080"], 60.0, 70.0)
        expected = max(0, 100 - (20 + 8 + 7 + 8))
        assert score == expected

    def test_score_floor_zero(self):
        score = agent._compute_score(100, ["8080"]*10, 100.0, 100.0)
        assert score == 0


# ── _count_ssh_failures ──────────────────────────────────────────────────

class TestCountSshFailures:
    SSH_LOG_PATHS = "/var/log/test_auth.log"

    @patch("os.path.exists", return_value=True)
    def test_counts_failed_password(self, mock_exists):
        log_content = (
            "Feb 10 10:00:00 host sshd[123]: Failed password for root from 10.0.0.1 port 22 ssh2\n"
            "Feb 10 10:01:00 host sshd[124]: Failed password for invalid user admin from 10.0.0.2 port 22 ssh2\n"
            "Feb 10 10:02:00 host sshd[125]: Accepted password for root from 10.0.0.1 port 22 ssh2\n"
        )
        with patch("builtins.open", mock_open(read_data=log_content)):
            with patch.dict(os.environ, {"SSH_LOG_PATHS": self.SSH_LOG_PATHS}, clear=False):
                assert agent._count_ssh_failures() == 2

    @patch("os.path.exists", return_value=True)
    def test_counts_authentication_failure(self, mock_exists):
        log_content = (
            "Feb 10 10:00:00 host sshd[123]: Authentication failure for root from 10.0.0.1 port 22\n"
            "Feb 10 10:01:00 host login[456]: authentication failure; logname= uid=0 euid=0 tty=ssh\n"
        )
        with patch("builtins.open", mock_open(read_data=log_content)):
            with patch.dict(os.environ, {"SSH_LOG_PATHS": self.SSH_LOG_PATHS}, clear=False):
                assert agent._count_ssh_failures() == 2

    @patch("os.path.exists", return_value=True)
    def test_mixed_log_lines(self, mock_exists):
        log_content = (
            "Feb 10 10:00:00 host sshd[123]: Failed password for root from 10.0.0.1 port 22 ssh2\n"
            "Feb 10 10:01:00 host sshd[124]: authentication failure; logname= uid=0\n"
            "Feb 10 10:02:00 host sshd[125]: Connection closed by 10.0.0.1 port 22\n"
            "Feb 10 10:03:00 host sshd[126]: Did not receive identification string from 10.0.0.2\n"
        )
        with patch("builtins.open", mock_open(read_data=log_content)):
            with patch.dict(os.environ, {"SSH_LOG_PATHS": self.SSH_LOG_PATHS}, clear=False):
                assert agent._count_ssh_failures() == 2

    @patch("os.path.exists", return_value=False)
    def test_no_log_files(self, mock_exists):
        assert agent._count_ssh_failures() == 0

    @patch("os.path.exists", return_value=True)
    def test_empty_log(self, mock_exists):
        with patch("builtins.open", mock_open(read_data="")):
            assert agent._count_ssh_failures() == 0

    @patch("os.path.exists", return_value=True)
    def test_oserror_handled(self, mock_exists):
        m = mock_open()
        m.side_effect = OSError("Permission denied")
        with patch("builtins.open", m):
            assert agent._count_ssh_failures() == 0


# ── _get_ram_usage_percent ───────────────────────────────────────────────

class TestGetRamUsagePercent:
    def test_typical_values(self):
        meminfo = "MemTotal:       8000000 kB\nMemFree:        1000000 kB\nMemAvailable:   4000000 kB\n"
        with patch("builtins.open", mock_open(read_data=meminfo)):
            pct = agent._get_ram_usage_percent()
            assert pct is not None
            assert abs(pct - 50.0) < 0.01  # (8000-4000)/8000*100 = 50

    def test_high_usage(self):
        meminfo = "MemTotal:       8000000 kB\nMemFree:         500000 kB\nMemAvailable:   1000000 kB\n"
        with patch("builtins.open", mock_open(read_data=meminfo)):
            pct = agent._get_ram_usage_percent()
            assert pct is not None
            assert abs(pct - 87.5) < 0.01

    def test_low_usage(self):
        meminfo = "MemTotal:       8000000 kB\nMemFree:        6000000 kB\nMemAvailable:   7500000 kB\n"
        with patch("builtins.open", mock_open(read_data=meminfo)):
            pct = agent._get_ram_usage_percent()
            assert pct is not None
            assert abs(pct - 6.25) < 0.01

    def test_missing_file_returns_none(self):
        with patch("builtins.open", side_effect=OSError("No such file")):
            assert agent._get_ram_usage_percent() is None

    def test_malformed_content_returns_none(self):
        with patch("builtins.open", mock_open(read_data="not a meminfo file\n")):
            assert agent._get_ram_usage_percent() is None

    def test_zero_total_returns_none(self):
        meminfo = "MemTotal:           0 kB\nMemAvailable:   4000000 kB\n"
        with patch("builtins.open", mock_open(read_data=meminfo)):
            assert agent._get_ram_usage_percent() is None


# ── _format_report ───────────────────────────────────────────────────────

class TestFormatReport:
    def test_perfect_score_no_recommendations(self):
        report = agent._format_report(100, 0, [], None, None)
        assert "Puntuación: 100/100" in report
        assert "Sistema estable" in report

    def test_ssh_failures_recommendation(self):
        report = agent._format_report(80, 10, [], None, None)
        assert "SSH fallos: 10" in report
        assert "deshabilitar login" in report

    def test_open_ports_recommendation(self):
        report = agent._format_report(90, 0, ["8080", "3306"], None, None)
        assert "Puertos abiertos: 8080, 3306" in report
        assert "cerrar servicios" in report

    def test_temperature_recommendation(self):
        report = agent._format_report(80, 0, [], 70.0, None)
        assert "Temperatura CPU: 70.0C" in report
        assert "refrigeraci" in report

    def test_ram_recommendation(self):
        report = agent._format_report(80, 0, [], None, 85.0)
        assert "RAM usado: 85.0%" in report
        assert "swap" in report

    def test_all_issues_present(self):
        report = agent._format_report(30, 15, ["8080"], 70.0, 85.0)
        assert "Puntuación: 30/100" in report
        assert "SSH fallos: 15" in report
        assert "Puertos abiertos: 8080" in report
        assert "Temperatura CPU: 70.0C" in report
        assert "RAM usado: 85.0%" in report
        assert "deshabilitar login" in report
        assert "cerrar servicios" in report
        assert "refrigeraci" in report
        assert "swap" in report

    def test_temperature_unknown(self):
        report = agent._format_report(90, 0, [], None, None)
        assert "Temperatura: desconocida" in report

    def test_ram_unknown(self):
        report = agent._format_report(90, 0, [], None, None)
        assert "RAM: desconocido" in report

    def test_no_ports(self):
        report = agent._format_report(100, 0, [], None, None)
        assert "ninguno" in report
