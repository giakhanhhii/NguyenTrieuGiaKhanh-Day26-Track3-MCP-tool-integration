import sqlite3
from typing import Any

from db_base import (
    DatabaseAdapter,
    ValidationError,
    ALLOWED_METRICS,
    _validate_identifier,
)
from init_db import DB_PATH, create_database


class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        if not __import__("os").path.exists(db_path):
            create_database(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        return [r["name"] for r in rows]

    def get_table_schema(self, table: str) -> list[dict]:
        _validate_identifier(table, "table name")
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table: {table!r}")
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [
            {
                "cid": r["cid"],
                "name": r["name"],
                "type": r["type"],
                "notnull": bool(r["notnull"]),
                "default": r["dflt_value"],
                "pk": bool(r["pk"]),
            }
            for r in rows
        ]

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict:
        known_cols = self._validate_table_and_columns(table, columns)
        col_sql = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        where_sql, params = self._build_where(table, filters, placeholder="?")

        order_sql = ""
        if order_by:
            _validate_identifier(order_by, "order_by column")
            if order_by not in known_cols:
                raise ValidationError(
                    f"Unknown order_by column {order_by!r} in table {table!r}"
                )
            order_sql = f'ORDER BY "{order_by}" {"DESC" if descending else "ASC"}'

        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        sql = f'SELECT {col_sql} FROM "{table}" {where_sql} {order_sql} LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return {
            "table": table,
            "count": len(rows),
            "rows": [dict(r) for r in rows],
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict:
        if not values:
            raise ValidationError("'values' must not be empty")
        self._validate_table_and_columns(table, list(values.keys()))

        cols = list(values.keys())
        col_sql = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join("?" * len(cols))
        sql = f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})'

        with self.connect() as conn:
            cursor = conn.execute(sql, [values[c] for c in cols])
            conn.commit()
            row_id = cursor.lastrowid

        return {"table": table, "inserted_id": row_id, "values": values}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict] | None = None,
        group_by: str | None = None,
    ) -> dict:
        metric = metric.lower()
        if metric not in ALLOWED_METRICS:
            raise ValidationError(
                f"Unsupported metric: {metric!r}. Allowed: {sorted(ALLOWED_METRICS)}"
            )

        known_cols = self._validate_table_and_columns(table)

        if metric == "count" and column is None:
            agg_expr = "COUNT(*)"
        else:
            if column is None:
                raise ValidationError(f"metric {metric!r} requires a 'column'")
            _validate_identifier(column, "column name")
            if column not in known_cols:
                raise ValidationError(
                    f"Unknown column {column!r} in table {table!r}"
                )
            agg_expr = f'{metric.upper()}("{column}")'

        where_sql, params = self._build_where(table, filters, placeholder="?")

        if group_by:
            _validate_identifier(group_by, "group_by column")
            if group_by not in known_cols:
                raise ValidationError(
                    f"Unknown group_by column {group_by!r} in table {table!r}"
                )
            sql = f'SELECT "{group_by}", {agg_expr} AS value FROM "{table}" {where_sql} GROUP BY "{group_by}"'
        else:
            sql = f'SELECT {agg_expr} AS value FROM "{table}" {where_sql}'

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "rows": [dict(r) for r in rows],
        }
