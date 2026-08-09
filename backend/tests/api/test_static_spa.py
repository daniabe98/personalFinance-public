from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app, packaged_spa


def _spa(root: Path) -> Path:
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text("<main>Personal Finance</main>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    return root


def test_packaged_spa_serves_assets_and_deep_links_without_masking_reserved_routes(
    tmp_path: Path, monkeypatch
) -> None:
    root = _spa(tmp_path / "installed-spa")
    monkeypatch.setenv("PERSONAL_FINANCE_SPA_DIR", str(root))
    app = create_app(readiness_probe=lambda: True)

    with TestClient(app) as client:
        asset = client.get("/assets/app.js")
        deep_link = client.get("/conciliar")
        missing_asset = client.get("/assets/missing.js")
        missing_api = client.get("/api/v1/not-a-route")
        missing_api_command = client.post("/api/v1/auth/bootstrap")
        missing_health = client.get("/health/not-a-route")

    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("text/javascript")
    assert deep_link.status_code == 200
    assert deep_link.headers["content-type"].startswith("text/html")
    assert "Personal Finance" in deep_link.text
    assert missing_asset.status_code == 404
    assert missing_api.status_code == 404
    assert missing_api_command.status_code == 404
    assert missing_health.status_code == 404


def test_packaged_spa_is_optional_and_resolves_an_installed_absolute_path(
    tmp_path: Path, monkeypatch
) -> None:
    root = _spa(tmp_path / "wheel" / "app" / "static")
    monkeypatch.setenv("PERSONAL_FINANCE_SPA_DIR", str(root))
    assert packaged_spa() == root.resolve()

    monkeypatch.setenv("PERSONAL_FINANCE_SPA_DIR", str(tmp_path / "missing"))
    assert packaged_spa() is None
    with TestClient(create_app(readiness_probe=lambda: True)) as client:
        assert client.get("/resumen").status_code == 404
