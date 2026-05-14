from typing import Any

from db_base import (
    DatabaseAdapter,
    ValidationError,
    ALLOWED_METRICS,
    _validate_identifier,
)

try:
    import psycopg2
    import psycopg2.extras
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL backend with the same MCP surface as SQLiteAdapter."""

    def __init__(self, dsn: str):
        if not _PG_AVAILABLE:
            raise RuntimeError(
                "psycopg2-binary is not installed. Run: pip install psycopg2-binary"
            )
        self.dsn = dsn

    def connect(self):
        conn = psycopg2.connect(self.dsn)
        conn.autocommit = False
        return conn

    def _cursor(self, conn):
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                return [r["tablename"] for r in cur.fetchall()]

    def get_table_schema(self, table: str) -> list[dict]:
        _validate_identifier(table, "table name")
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table: {table!r}")
        with self.connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT
                        ordinal_position - 1 AS cid,
                        column_name        AS name,
                        data_type          AS type,
                        (is_nullable = 'NO') AS notnull,
                        column_default     AS "default",
                        (column_name IN (
                            SELECT kcu.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                              ON tc.constraint_name = kcu.constraint_name
                             AND tc.table_name = kcu.table_name
                            WHERE tc.constraint_type = 'PRIMARY KEY'
                              AND tc.table_name = %s
                        )) AS pk
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position
                    """,
                    (table, table),
                )
                return [dict(r) for r in cur.fetchall()]

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
        where_sql, params = self._build_where(table, filters, placeholder="%s")

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
        sql = f'SELECT {col_sql} FROM "{table}" {where_sql} {order_sql} LIMIT %s OFFSET %s'
        params.extend([limit, offset])

        with self.connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]

        return {
            "table": table,
            "count": len(rows),
            "rows": rows,
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict:
        if not values:
            raise ValidationError("'values' must not be empty")
        self._validate_table_and_columns(table, list(values.keys()))

        cols = list(values.keys())
        col_sql = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders}) RETURNING id'

        with self.connect() as conn:
            with self._cursor(conn) as cur:
                cur.execute(sql, [values[c] for c in cols])
                row = cur.fetchone()
                conn.commit()
                row_id = row["id"] if row else None

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

        where_sql, params = self._build_where(table, filters, placeholder="%s")

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
            with self._cursor(conn) as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "rows": rows,
        }
