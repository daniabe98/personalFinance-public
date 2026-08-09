"""Create isolated synthetic E2E state and ephemeral loopback TLS material."""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic.config import Config
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from alembic import command
from app.main import create_app
from app.shared.config import Settings


def _migration_config(database_url: str) -> Config:
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _certificate(root: Path) -> tuple[Path, Path, Path, str]:
    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PF E2E CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=12))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = root / "ca.crt"
    cert_path = root / "server.crt"
    key_path = root / "server.key"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    spki = leaf_cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return (
        ca_path,
        cert_path,
        key_path,
        base64.b64encode(hashlib.sha256(spki).digest()).decode(),
    )


def prepare(root: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=False)
    database = root / "finance.sqlite3"
    database_url = f"sqlite:///{database.as_posix()}"
    command.upgrade(_migration_config(database_url), "head")
    settings = Settings(
        database_url=database_url,
        secret_key="e2e-secret-material-is-local-only-1234567890",
        domestic_timezone="Europe/Madrid",
        backup_retention=3,
    )
    app = create_app(settings=settings, allowed_origin="https://127.0.0.1")
    app.state.identity_service.bootstrap(
        username="owner",
        password="Synthetic-e2e-password-42!",
        space_name="Synthetic household",
    )
    ca, cert, key, spki = _certificate(root)
    return {
        "root": str(root),
        "database_url": database_url,
        "ca": str(ca),
        "cert": str(cert),
        "key": str(key),
        "spki": spki,
        "username": "owner",
        "password": "Synthetic-e2e-password-42!",
        "secret_key": "e2e-secret-material-is-local-only-1234567890",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
