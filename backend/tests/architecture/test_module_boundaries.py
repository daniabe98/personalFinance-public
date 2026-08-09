from __future__ import annotations

import ast
from pathlib import Path

MODULES = ("identity", "ledger", "reconciliation", "reporting", "audit", "recovery")
APP_ROOT = Path(__file__).parents[2] / "app"
FORBIDDEN_FRAMEWORKS = ("fastapi", "sqlalchemy")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_all_bounded_context_packages_exist() -> None:
    for module in MODULES:
        module_root = APP_ROOT / module
        assert (module_root / "__init__.py").is_file()
        for layer in ("domain", "application", "ports", "adapters"):
            assert (module_root / layer / "__init__.py").is_file()


def test_domain_and_application_are_framework_independent() -> None:
    for module in MODULES:
        for layer in ("domain", "application"):
            for path in (APP_ROOT / module / layer).rglob("*.py"):
                imports = _imports(path)
                assert not any(
                    imported == framework or imported.startswith(f"{framework}.")
                    for imported in imports
                    for framework in FORBIDDEN_FRAMEWORKS
                ), f"{path} imports an outer framework"


def test_modules_do_not_import_another_modules_adapters() -> None:
    for module in MODULES:
        for path in (APP_ROOT / module).rglob("*.py"):
            imports = _imports(path)
            forbidden = {f"app.{other}.adapters" for other in MODULES if other != module}
            assert not any(
                imported == prefix or imported.startswith(f"{prefix}.")
                for imported in imports
                for prefix in forbidden
            ), f"{path} reaches into another module's adapters"
