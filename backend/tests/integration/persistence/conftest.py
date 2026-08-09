from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine

from alembic import command


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'finance.db').as_posix()}"


def alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[3] / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def migrated_engine(database_url: str) -> Iterator[Engine]:
    from app.shared.database import create_engine

    command.upgrade(alembic_config(database_url), "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def mapped_engine(database_url: str) -> Iterator[Engine]:
    from app.shared import models_control, models_identity, models_ledger
    from app.shared.database import Base, create_engine

    del models_control, models_identity, models_ledger
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
