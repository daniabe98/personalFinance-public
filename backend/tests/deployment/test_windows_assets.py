from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WINDOWS_DEPLOY = ROOT / "deploy" / "windows"


def text(name: str) -> str:
    return (WINDOWS_DEPLOY / name).read_text(encoding="utf-8")


def test_only_native_windows_deployment_assets_are_shipped() -> None:
    expected = {
        "appsettings.example.json",
        "Backup-PersonalFinance.ps1",
        "Install-PersonalFinance.ps1",
        "Start-PersonalFinance.ps1",
        "Test-PersonalFinance.ps1",
        "Uninstall-PersonalFinance.ps1",
    }
    assert {path.name for path in WINDOWS_DEPLOY.iterdir()} == expected

    removed = (
        "deploy/personal-finance.service",
        "deploy/personal-finance-backup.service",
        "deploy/personal-finance-backup.timer",
        "deploy/personal-finance.env.example",
        "scripts/create-lan-certificate.sh",
    )
    assert all(not (ROOT / path).exists() for path in removed)


def test_example_configuration_enables_only_explicit_http_lan_mode() -> None:
    config = json.loads(text("appsettings.example.json"))

    assert config == {
        "PF_ALLOWED_ORIGIN": "http://192.168.1.50:8080",
        "PF_BACKUP_DIRECTORY": "C:\\ProgramData\\PersonalFinance\\backups",
        "PF_BACKUP_RETENTION": "7",
        "PF_DATABASE_URL": ("sqlite:///C:/ProgramData/PersonalFinance/data/personal-finance.db"),
        "PF_DOMESTIC_TIMEZONE": "Europe/Madrid",
        "PF_SECRET_KEY": "<generated-during-installation>",
        "PF_TRANSPORT_MODE": "http_lan",
    }


def test_powershell_scripts_parse_on_windows_powershell() -> None:
    shell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if shell is None:
        pytest.skip("PowerShell parser is available in the Windows deployment job")

    for script in WINDOWS_DEPLOY.glob("*.ps1"):
        command = (
            "$errors = $null; "
            f"[void][System.Management.Automation.Language.Parser]::ParseFile('{script}', "
            "[ref]$null, [ref]$errors); "
            "if ($errors.Count -gt 0) { $errors | Out-String | Write-Error; exit 1 }"
        )
        subprocess.run(
            [shell, "-NoProfile", "-NonInteractive", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
        )


def test_start_and_backup_scripts_load_process_environment_without_secret_arguments() -> None:
    start = text("Start-PersonalFinance.ps1")
    backup = text("Backup-PersonalFinance.ps1")

    for script in (start, backup):
        assert "ConvertFrom-Json" in script
        assert "SetEnvironmentVariable" in script
        assert '"Process"' in script
        assert "--secret" not in script.lower()
        assert "@(0, 5) -contains" in script

    assert start.index('personal-finance.exe" migrate') < start.index(
        'personal-finance.exe" backup --if-due'
    )
    assert "--host 0.0.0.0" in start
    assert "[int]$Port = 8080" in start
    assert "--port $Port" in start


def test_installer_requires_private_ipv4_and_builds_uv_managed_runtime() -> None:
    installer = text("Install-PersonalFinance.ps1")

    assert "Test-PrivateIPv4" in installer
    assert "uv python install 3.13" in installer
    assert "UV_PYTHON_INSTALL_DIR" in installer
    assert "--install-dir $pythonInstallRoot" in installer
    assert "uv python find --managed-python --no-project 3.13" in installer
    assert "$uvFindExitCode = $LASTEXITCODE" in installer
    assert "$managedPythonOutput | Select-Object -First 1" in installer
    assert installer.index("$uvFindExitCode = $LASTEXITCODE") < installer.index(
        "$managedPythonOutput | Select-Object -First 1"
    )
    assert 'SetEnvironmentVariable("VIRTUAL_ENV", $null, "Process")' in installer
    assert "uv venv --clear --python $managedPython" in installer
    assert "uv pip install --link-mode copy --python" in installer
    assert "Stop-ScheduledTask -TaskName $taskName" in installer
    assert "Get-CimInstance Win32_Process" in installer
    assert "Invoke-CimMethod -InputObject $runtimeProcess -MethodName Terminate" in installer
    assert installer.index("Stop-ScheduledTask") < installer.index(
        "uv venv --clear --python $managedPython"
    )
    assert "ProgramFiles" in installer
    assert "ProgramData" in installer
    assert "RandomNumberGenerator" in installer
    assert "ConvertTo-Json" in installer
    assert "@(0, 2) -notcontains $bootstrapExitCode" in installer


def test_installer_applies_acl_tasks_and_private_local_subnet_firewall() -> None:
    installer = text("Install-PersonalFinance.ps1")

    for principal_sid in ("S-1-5-18", "S-1-5-32-544", "S-1-5-19"):
        assert principal_sid in installer
    assert "BUILTIN\\Administrators" not in installer
    assert "NT AUTHORITY\\LOCAL SERVICE" not in installer
    assert "icacls.exe" in installer
    assert "/inheritance:r" in installer
    assert '"*S-1-5-19:(OI)(CI)RX"' in installer
    assert '"PersonalFinance-App"' in installer
    assert '"PersonalFinance-Backup"' in installer
    assert "New-ScheduledTaskTrigger -AtStartup" in installer
    assert "New-ScheduledTaskTrigger -Daily" in installer
    assert "-StartWhenAvailable" in installer
    assert "-RestartCount" in installer
    assert "New-NetFirewallRule" in installer
    assert "-Profile Private" in installer
    assert "-RemoteAddress LocalSubnet" in installer
    assert "-Protocol TCP" in installer
    assert "-LocalPort $Port" in installer


def test_diagnostics_cover_tasks_firewall_health_backup_and_acl() -> None:
    diagnostic = text("Test-PersonalFinance.ps1")

    assert 'Get-ScheduledTask -TaskName "PersonalFinance-App"' in diagnostic
    assert 'Get-ScheduledTask -TaskName "PersonalFinance-Backup"' in diagnostic
    assert "Get-NetFirewallRule" in diagnostic
    assert "Get-Acl" in diagnostic
    assert "SecurityIdentifier" in diagnostic
    assert "S-1-5-32-544" in diagnostic
    assert "/health/ready" in diagnostic
    assert "Backup-PersonalFinance.ps1" in diagnostic


def test_uninstaller_removes_runtime_but_never_data_or_backups() -> None:
    uninstaller = text("Uninstall-PersonalFinance.ps1")

    assert "Unregister-ScheduledTask" in uninstaller
    assert "Remove-NetFirewallRule" in uninstaller
    assert "Remove-Item -LiteralPath $InstallRoot -Recurse" in uninstaller
    assert "Remove-Item -LiteralPath $DataRoot" not in uninstaller
    assert "preserved" in uninstaller.lower()


def test_runbooks_describe_windows_only_operation_and_confirmed_hitl_guard() -> None:
    install = (ROOT / "docs/runbooks/install-lan.md").read_text(encoding="utf-8")
    operations = (ROOT / "docs/runbooks/operations.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "docs/runbooks/acceptance.md").read_text(encoding="utf-8")

    combined = "\n".join((install, operations, acceptance)).lower()
    assert "systemd" not in combined
    assert "linux" not in combined
    assert "personalfinance-app" in combined
    assert "personalfinance-backup" in combined
    assert "localsubnet" in combined
    assert "http://<ip-privada>:8080" in combined
    assert "aceptación hitl confirmada" in acceptance.lower()
    assert "confirmación expresa de la persona operadora: `confirmado`" in acceptance.lower()
    assert "sin hostname, ip, usuario" in acceptance.lower()
    assert "<PASS|FAIL>" in acceptance
