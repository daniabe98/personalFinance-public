from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_application_and_backup_units_are_hardened_and_consistent() -> None:
    app = text("deploy/personal-finance.service")
    backup = text("deploy/personal-finance-backup.service")
    timer = text("deploy/personal-finance-backup.timer")
    env = text("deploy/personal-finance.env.example")

    for unit in (app, backup):
        assert "User=personal-finance" in unit
        assert "SuccessExitStatus=5" in unit
        assert "NoNewPrivileges=true" in unit
        assert "ProtectSystem=strict" in unit
        assert "UMask=0077" in unit
        assert "ReadWritePaths=/var/lib/personal-finance /var/backups/personal-finance" in unit
        assert "personal-finance backup --if-due" in unit
    assert "ExecStartPre=" in app
    assert "personal-finance migrate" in app
    assert app.index("personal-finance migrate") < app.index("personal-finance backup --if-due")
    assert "--ssl-certfile ${PF_TLS_CERT}" in app
    assert "--ssl-keyfile ${PF_TLS_KEY}" in app
    assert "--port 8443" in app
    assert "--port 80" not in app
    assert "Type=oneshot" in backup
    assert "Persistent=true" in timer
    assert "PF_TLS_CERT=" in env
    assert "PF_TLS_KEY=" in env
    assert "PF_BACKUP_DIRECTORY=/var/backups/personal-finance" in env


def test_certificate_script_rejects_repo_destinations_and_defines_all_sans() -> None:
    script = text("scripts/create-lan-certificate.sh")
    assert "TLS material must be outside the repository" in script
    assert "subjectAltName=DNS:$dns_name,IP:$ip_address,IP:127.0.0.1,DNS:localhost" in script
    assert "umask 077" in script
    assert 'chmod 600 "$output/ca.key" "$output/server.key"' in script
    assert 'cat >"$output/server.ext"' in script
    assert "ca.key" not in "\n".join(
        line for line in script.splitlines() if line.startswith("echo ")
    )


def test_runbooks_match_units_and_preserve_the_hitl_guard() -> None:
    install = text("docs/runbooks/install-lan.md")
    operations = text("docs/runbooks/operations.md")
    acceptance = text("docs/runbooks/acceptance.md")
    assert "personal-finance.service" in install
    assert "personal-finance migrate" in install
    assert "personal-finance bootstrap" in install
    assert "personal-finance-backup.timer" in install
    assert "puerto 80 debe permanecer cerrado" in install
    assert "backup --if-due" in operations
    assert "backup-restore.md" in operations
    assert "No existe restauración HTTP" in operations
    assert "pendiente de evidencia HITL" in acceptance
    assert "No cambies `PENDIENTE` a `CONFIRMADO` desde Windows" in acceptance
    assert "<PASS|FAIL>" in acceptance
