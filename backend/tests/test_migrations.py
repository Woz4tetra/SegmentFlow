"""Migration script end-to-end checks on a simulated old database."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect


def _expected_tables() -> set[str]:
    return {
        "projects",
        "labels",
        "images",
        "labeled_points",
        "masks",
        "stats",
        "user_settings",
    }


def _has_fk(inspector, table: str, column: str, target: str) -> bool:
    fks = inspector.get_foreign_keys(table)
    return any(
        column in fk.get("constrained_columns", []) and fk.get("referred_table") == target
        for fk in fks
    )


@pytest.mark.integration
def test_apply_migrations_on_old_sqlite_db(tmp_path: Path) -> None:
    """Running the migration script on an old DB should create all tables and FKs."""

    db_path = tmp_path / "old.db"

    # Simulate an old schema with only the projects table present.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
            """
        )
        conn.commit()

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:////{db_path}"
    env.setdefault("SEGMENTFLOW_SQLITE_POOL", "NullPool")

    # Run migrations via the dedicated script in a fresh process to honor env vars.
    subprocess.check_call(
        [sys.executable, "-m", "app.scripts.apply_migrations"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
    )

    # Inspect resulting schema using a synchronous engine for assertions.
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)

    tables = set(inspector.get_table_names())
    assert _expected_tables().issubset(tables)

    assert _has_fk(inspector, "labels", "project_id", "projects")
    assert _has_fk(inspector, "images", "project_id", "projects")
    assert _has_fk(inspector, "labeled_points", "image_id", "images")
    assert _has_fk(inspector, "labeled_points", "label_id", "labels")
    assert _has_fk(inspector, "masks", "image_id", "images")
    assert _has_fk(inspector, "masks", "label_id", "labels")
    assert _has_fk(inspector, "stats", "project_id", "projects")
    assert _has_fk(inspector, "stats", "image_id", "images")

    engine.dispose()
