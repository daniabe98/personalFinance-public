from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
START_SCRIPT = ROOT / "deploy" / "windows" / "Start-PersonalFinance.ps1"
PASSWORD = "Synthetic-Windows-smoke-password-42!"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows deployment smoke")


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _request(
    url: str,
    *,
    data: dict[str, str] | None = None,
    origin: str | None = None,
    cookie: str | None = None,
) -> urllib.request.Request:
    encoded = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=encoded)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if origin is not None:
        request.add_header("Origin", origin)
    if cookie is not None:
        request.add_header("Cookie", cookie)
    return request


def _wait_until_ready(origin: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"Windows wrapper stopped early: {stdout}\n{stderr}")
        try:
            with urllib.request.urlopen(f"{origin}/health/ready", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    raise AssertionError("Windows wrapper did not become ready")


def test_built_wheel_serves_explicit_http_lan_session_flow(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    uv = shutil.which("uv.exe") or shutil.which("uv")
    assert powershell is not None
    assert uv is not None

    wheelhouse = tmp_path / "wheelhouse"
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(wheelhouse)],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheelhouse.glob("personal_finance-*.whl"))
    install_root = tmp_path / "program-files" / "PersonalFinance"
    data_root = tmp_path / "program-data" / "PersonalFinance"
    venv = install_root / "venv"
    python_install_root = install_root / "python"
    uv_environment = os.environ.copy()
    for inherited_environment in ("VIRTUAL_ENV", "CONDA_PREFIX", "UV_PROJECT_ENVIRONMENT"):
        uv_environment.pop(inherited_environment, None)
    uv_environment["UV_PYTHON_INSTALL_DIR"] = str(python_install_root)
    subprocess.run(
        [
            uv,
            "python",
            "install",
            "3.13",
            "--install-dir",
            str(python_install_root),
            "--no-bin",
            "--no-registry",
        ],
        env=uv_environment,
        check=True,
        capture_output=True,
        text=True,
    )
    managed_python = subprocess.run(
        [uv, "python", "find", "--managed-python", "--no-project", "3.13"],
        env=uv_environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert Path(managed_python).is_relative_to(python_install_root)
    subprocess.run(
        [uv, "venv", "--clear", "--python", managed_python, str(venv)],
        env=uv_environment,
        check=True,
        capture_output=True,
        text=True,
    )
    python = venv / "Scripts" / "python.exe"
    subprocess.run(
        [uv, "pip", "install", "--link-mode", "copy", "--python", str(python), str(wheel)],
        env=uv_environment,
        check=True,
        capture_output=True,
        text=True,
    )

    for directory in (
        data_root / "config",
        data_root / "data",
        data_root / "backups",
        data_root / "logs",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    origin = f"http://127.0.0.1:{port}"
    database_url = f"sqlite:///{(data_root / 'data' / 'smoke.db').as_posix()}"
    config = {
        "PF_ALLOWED_ORIGIN": origin,
        "PF_BACKUP_DIRECTORY": str(data_root / "backups"),
        "PF_BACKUP_RETENTION": "2",
        "PF_DATABASE_URL": database_url,
        "PF_DOMESTIC_TIMEZONE": "Europe/Madrid",
        "PF_SECRET_KEY": "windows-smoke-secret-material-1234567890",
        "PF_TRANSPORT_MODE": "http_lan",
    }
    (data_root / "config" / "appsettings.json").write_text(json.dumps(config), encoding="utf-8")
    environment = os.environ | config
    executable = venv / "Scripts" / "personal-finance.exe"
    subprocess.run([executable, "migrate"], env=environment, check=True, capture_output=True)
    bootstrap = (
        "from app.cli import app; "
        f"raise SystemExit(app(['bootstrap', '--username', 'owner', '--space-name', "
        f"'Synthetic household'], password_prompt=lambda _: {PASSWORD!r}))"
    )
    subprocess.run([python, "-c", bootstrap], env=environment, check=True, capture_output=True)

    process = subprocess.Popen(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(START_SCRIPT),
            "-InstallRoot",
            str(install_root),
            "-DataRoot",
            str(data_root),
            "-Port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until_ready(origin, process)

        with pytest.raises(urllib.error.HTTPError) as unauthorized:
            urllib.request.urlopen(f"{origin}/api/v1/auth/session", timeout=5)
        assert unauthorized.value.code == 401
        unauthorized.value.close()

        login = _request(
            f"{origin}/api/v1/auth/login",
            data={"username": "owner", "password": PASSWORD},
            origin=origin,
        )
        with urllib.request.urlopen(login, timeout=5) as response:
            assert response.status == 200
            set_cookie = response.headers["Set-Cookie"]
        assert set_cookie.startswith("pf_session=")
        assert "HttpOnly" in set_cookie
        assert "SameSite=strict" in set_cookie
        assert "Secure" not in set_cookie

        session_cookie = set_cookie.split(";", maxsplit=1)[0]
        with urllib.request.urlopen(
            _request(f"{origin}/api/v1/auth/session", cookie=session_cookie), timeout=5
        ) as response:
            assert response.status == 200
    finally:
        if process.poll() is None:
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
            )
        process.communicate(timeout=10)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
