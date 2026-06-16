"""Offline checks for Phase 1 database schema."""

from pathlib import Path


def test_initial_migration_defines_core_tables():
    sql = (Path(__file__).resolve().parents[1] / "app/db/migrations/001_initial.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS vessel" in sql
    assert "CREATE TABLE IF NOT EXISTS ais_position" in sql
    assert "GEOMETRY(Point, 4326)" in sql
    assert "ix_pos_geom" in sql
