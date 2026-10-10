import os
import sqlite3
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_new_scripts_have_valid_bash_syntax():
    root = _repo_root()
    scripts = [
        root / "scripts/bootstrap_debian_arm64.sh",
        root / "scripts/backup_state.sh",
        root / "scripts/restore_state.sh",
        root / "scripts/health_watchdog.sh",
        root / "scripts/update_safe.sh",
    ]
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"{script}: {result.stderr}"


def test_backup_and_restore_roundtrip(tmp_path: Path):
    install_root = tmp_path / "opt"
    data_dir = install_root / "data"
    reports_dir = install_root / "reports"
    backups_dir = install_root / "backups"
    data_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)
    backups_dir.mkdir(parents=True)

    db_path = data_dir / "history.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE metrics(id INTEGER PRIMARY KEY, score INTEGER)")
    con.execute("INSERT INTO metrics(score) VALUES (99)")
    con.commit()
    con.close()

    (reports_dir / "report.txt").write_text("ok", encoding="utf-8")

    env = os.environ.copy()
    env["EDGE_INSTALL_ROOT"] = str(install_root)

    backup_script = _repo_root() / "scripts/backup_state.sh"
    backup_result = subprocess.run([str(backup_script)], env=env, capture_output=True, text=True, check=False)
    assert backup_result.returncode == 0, backup_result.stderr
    backup_path = Path(backup_result.stdout.strip())
    assert (backup_path / "SHA256SUMS").exists()

    db_path.unlink()
    (reports_dir / "report.txt").unlink()

    restore_script = _repo_root() / "scripts/restore_state.sh"
    restore_result = subprocess.run(
        [str(restore_script), str(backup_path)], env=env, capture_output=True, text=True, check=False
    )
    assert restore_result.returncode == 0, restore_result.stderr

    con = sqlite3.connect(db_path)
    row = con.execute("SELECT score FROM metrics LIMIT 1").fetchone()
    con.close()
    assert row and row[0] == 99
    assert (reports_dir / "report.txt").read_text(encoding="utf-8") == "ok"


def test_update_script_blocks_main_without_explicit_override():
    script = _repo_root() / "scripts/update_safe.sh"
    result = subprocess.run([str(script), "--channel", "main", "--dry-run"], capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "bloqueada por seguridad" in result.stderr


def test_health_watchdog_restart_path_is_safe_with_mock_restart(tmp_path: Path):
    script = _repo_root() / "scripts/health_watchdog.sh"
    env = os.environ.copy()
    env["EDGE_HEALTH_URL"] = "http://127.0.0.1:9/unreachable"
    env["EDGE_RESTART_CMD"] = "/bin/true"
    env["EDGE_DB_PATH"] = str(tmp_path / "missing.db")

    result = subprocess.run([str(script)], env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0
