import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from init_db import create_database
from db import SQLiteAdapter
from db_base import ValidationError

# ── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def adapter(tmp_path):
    db_path = str(tmp_path / "test.db")
    create_database(db_path)
    return SQLiteAdapter(db_path)


# ── PostgreSQL fixture (skip if unavailable) ───────────────────────────────

def _pg_dsn():
    return os.getenv("POSTGRES_DSN", "")


@pytest.fixture
def pg_adapter():
    dsn = _pg_dsn()
    if not dsn:
        pytest.skip("POSTGRES_DSN not set — skipping PostgreSQL tests")
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed")

    from db_postgres import PostgreSQLAdapter
    from init_pg import PG_SCHEMA_SQL, PG_SEED_SQL

    pg = PostgreSQLAdapter(dsn)

    conn = pg.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(PG_SCHEMA_SQL)
            cur.execute(PG_SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    yield pg

    # Teardown — drop and recreate so the next run starts clean
    conn = pg.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS enrollments, students, courses CASCADE")
        conn.commit()
    finally:
        conn.close()


# ── SQLite: search ─────────────────────────────────────────────────────────

class TestSearch:
    def test_returns_all_students(self, adapter):
        result = adapter.search("students")
        assert result["count"] > 0
        assert "rows" in result

    def test_filter_by_cohort(self, adapter):
        result = adapter.search("students", filters=[{"column": "cohort", "operator": "eq", "value": "A1"}])
        for row in result["rows"]:
            assert row["cohort"] == "A1"

    def test_selected_columns_only(self, adapter):
        result = adapter.search("students", columns=["name", "score"])
        for row in result["rows"]:
            assert set(row.keys()) == {"name", "score"}

    def test_limit_and_offset(self, adapter):
        first = adapter.search("students", limit=2, offset=0)
        second = adapter.search("students", limit=2, offset=2)
        assert first["rows"] != second["rows"]
        assert len(first["rows"]) <= 2

    def test_order_by_descending(self, adapter):
        result = adapter.search("students", order_by="score", descending=True)
        scores = [r["score"] for r in result["rows"]]
        assert scores == sorted(scores, reverse=True)

    def test_operator_gte(self, adapter):
        result = adapter.search("students", filters=[{"column": "score", "operator": "gte", "value": 90}])
        for row in result["rows"]:
            assert row["score"] >= 90

    def test_operator_like(self, adapter):
        result = adapter.search("students", filters=[{"column": "name", "operator": "like", "value": "A%"}])
        for row in result["rows"]:
            assert row["name"].startswith("A")

    def test_operator_in(self, adapter):
        result = adapter.search("students", filters=[{"column": "cohort", "operator": "in", "value": ["A1", "B2"]}])
        for row in result["rows"]:
            assert row["cohort"] in ("A1", "B2")

    def test_unknown_table_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.search("ghost_table")

    def test_unknown_column_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.search("students", columns=["ghost"])

    def test_unsupported_operator_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.search("students", filters=[{"column": "cohort", "operator": "regex", "value": "A"}])

    def test_invalid_identifier_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.search("students; DROP TABLE students--")


# ── SQLite: insert ─────────────────────────────────────────────────────────

class TestInsert:
    def test_insert_and_return_id(self, adapter):
        result = adapter.insert("students", {
            "name": "New Student",
            "email": "new@test.io",
            "cohort": "Z9",
            "score": 77.0,
        })
        assert result["inserted_id"] is not None
        assert result["values"]["name"] == "New Student"

    def test_inserted_row_is_searchable(self, adapter):
        adapter.insert("students", {
            "name": "Unique Name",
            "email": "unique@test.io",
            "cohort": "Z9",
            "score": 55.0,
        })
        result = adapter.search("students", filters=[{"column": "email", "operator": "eq", "value": "unique@test.io"}])
        assert result["count"] == 1

    def test_empty_values_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.insert("students", {})

    def test_unknown_column_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.insert("students", {"ghost_col": "x", "email": "x@x.io", "name": "X", "cohort": "X"})

    def test_unknown_table_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.insert("ghost", {"col": "val"})


# ── SQLite: aggregate ──────────────────────────────────────────────────────

class TestAggregate:
    def test_count_star(self, adapter):
        result = adapter.aggregate("students", "count")
        assert result["rows"][0]["value"] > 0

    def test_count_with_column(self, adapter):
        result = adapter.aggregate("students", "count", column="score")
        assert result["rows"][0]["value"] > 0

    def test_avg(self, adapter):
        result = adapter.aggregate("students", "avg", column="score")
        val = result["rows"][0]["value"]
        assert 0 < val <= 100

    def test_sum(self, adapter):
        result = adapter.aggregate("courses", "sum", column="credits")
        assert result["rows"][0]["value"] > 0

    def test_min_max(self, adapter):
        mn = adapter.aggregate("students", "min", column="score")
        mx = adapter.aggregate("students", "max", column="score")
        assert mn["rows"][0]["value"] <= mx["rows"][0]["value"]

    def test_group_by(self, adapter):
        result = adapter.aggregate("students", "count", group_by="cohort")
        assert len(result["rows"]) > 1
        for row in result["rows"]:
            assert "cohort" in row
            assert "value" in row

    def test_unsupported_metric_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.aggregate("students", "median")

    def test_avg_without_column_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.aggregate("students", "avg")

    def test_unknown_table_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.aggregate("ghost", "count")

    def test_with_filter(self, adapter):
        result = adapter.aggregate(
            "students", "avg", column="score",
            filters=[{"column": "cohort", "operator": "eq", "value": "A1"}]
        )
        assert result["rows"][0]["value"] is not None


# ── SQLite: schema ─────────────────────────────────────────────────────────

class TestSchema:
    def test_list_tables(self, adapter):
        tables = adapter.list_tables()
        assert set(tables) >= {"students", "courses", "enrollments"}

    def test_get_table_schema(self, adapter):
        cols = adapter.get_table_schema("students")
        names = [c["name"] for c in cols]
        assert "id" in names
        assert "name" in names
        assert "cohort" in names

    def test_unknown_table_raises(self, adapter):
        with pytest.raises(ValidationError):
            adapter.get_table_schema("nonexistent")


# ── PostgreSQL: shared surface (skipped if no PG) ─────────────────────────

class TestPostgresAdapter:
    def test_list_tables(self, pg_adapter):
        tables = pg_adapter.list_tables()
        assert "students" in tables

    def test_search(self, pg_adapter):
        result = pg_adapter.search("students")
        assert result["count"] > 0

    def test_filter(self, pg_adapter):
        result = pg_adapter.search(
            "students",
            filters=[{"column": "cohort", "operator": "eq", "value": "A1"}],
        )
        for row in result["rows"]:
            assert row["cohort"] == "A1"

    def test_insert(self, pg_adapter):
        result = pg_adapter.insert("students", {
            "name": "PG Test",
            "email": "pgtest@test.io",
            "cohort": "Z9",
            "score": 80.0,
        })
        assert result["inserted_id"] is not None

    def test_aggregate_count(self, pg_adapter):
        result = pg_adapter.aggregate("students", "count")
        assert result["rows"][0]["value"] > 0

    def test_aggregate_avg(self, pg_adapter):
        result = pg_adapter.aggregate("students", "avg", column="score")
        assert result["rows"][0]["value"] > 0

    def test_aggregate_group_by(self, pg_adapter):
        result = pg_adapter.aggregate("students", "count", group_by="cohort")
        assert len(result["rows"]) > 0

    def test_unknown_table_raises(self, pg_adapter):
        with pytest.raises(ValidationError):
            pg_adapter.search("ghost")

    def test_bad_metric_raises(self, pg_adapter):
        with pytest.raises(ValidationError):
            pg_adapter.aggregate("students", "median")
