from abc import ABC, abstractmethod
import re
from typing import Any

ALLOWED_OPERATORS = {"eq", "ne", "lt", "lte", "gt", "gte", "like", "in"}
ALLOWED_METRICS = {"count", "avg", "sum", "min", "max"}

_OP_MAP = {
    "eq": "=",
    "ne": "!=",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
    "like": "LIKE",
    "in": "IN",
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


def _validate_identifier(name: str, label: str = "identifier") -> None:
    if not _IDENTIFIER_RE.match(name):
        raise ValidationError(f"Invalid {label}: {name!r}")


class DatabaseAdapter(ABC):
    """Shared interface for all database backends (SQLite, PostgreSQL, …)."""

    @abstractmethod
    def list_tables(self) -> list[str]: ...

    @abstractmethod
    def get_table_schema(self, table: str) -> list[dict]: ...

    @abstractmethod
    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict: ...

    @abstractmethod
    def insert(self, table: str, values: dict[str, Any]) -> dict: ...

    @abstractmethod
    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict] | None = None,
        group_by: str | None = None,
    ) -> dict: ...

    # ── shared helpers ──────────────────────────────────────────────────────

    def _validate_table_and_columns(
        self, table: str, columns: list[str] | None = None
    ) -> list[str]:
        _validate_identifier(table, "table name")
        known = self.list_tables()
        if table not in known:
            raise ValidationError(f"Unknown table: {table!r}")
        schema_cols = {c["name"] for c in self.get_table_schema(table)}
        if columns:
            for col in columns:
                _validate_identifier(col, "column name")
                if col not in schema_cols:
                    raise ValidationError(
                        f"Unknown column {col!r} in table {table!r}"
                    )
        return list(schema_cols)

    def _build_where(
        self, table: str, filters: list[dict] | None, placeholder: str = "?"
    ) -> tuple[str, list]:
        """Build a WHERE clause. placeholder is '?' for SQLite or '%s' for PostgreSQL."""
        if not filters:
            return "", []
        schema_cols = {c["name"] for c in self.get_table_schema(table)}
        clauses, params = [], []
        for f in filters:
            col = f.get("column")
            op = f.get("operator", "eq")
            val = f.get("value")
            if col is None:
                raise ValidationError("Filter missing 'column'")
            _validate_identifier(col, "column name")
            if col not in schema_cols:
                raise ValidationError(
                    f"Unknown column {col!r} in table {table!r}"
                )
            if op not in ALLOWED_OPERATORS:
                raise ValidationError(
                    f"Unsupported operator: {op!r}. Allowed: {sorted(ALLOWED_OPERATORS)}"
                )
            sql_op = _OP_MAP[op]
            if op == "in":
                if not isinstance(val, list):
                    raise ValidationError("'in' operator requires a list value")
                ph = ", ".join([placeholder] * len(val))
                clauses.append(f'"{col}" {sql_op} ({ph})')
                params.extend(val)
            else:
                clauses.append(f'"{col}" {sql_op} {placeholder}')
                params.append(val)
        return "WHERE " + " AND ".join(clauses), params
