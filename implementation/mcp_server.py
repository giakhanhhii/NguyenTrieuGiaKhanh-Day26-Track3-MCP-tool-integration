import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier, AccessToken
from db_base import ValidationError
from init_db import create_database, DB_PATH


# ── auth provider ──────────────────────────────────────────────────────────

class ApiKeyAuth(TokenVerifier):
    """Validates a static Bearer token read from MCP_API_KEY."""

    def __init__(self, api_key: str, base_url: str):
        super().__init__(base_url=base_url)
        self._key = api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self._key:
            return AccessToken(token=token, client_id="api-key-client", scopes=[])
        return None


# ── adapter factory ────────────────────────────────────────────────────────

def _build_adapter():
    backend = os.getenv("DB_BACKEND", "sqlite").lower()
    if backend == "postgres":
        dsn = os.getenv("POSTGRES_DSN")
        if not dsn:
            raise RuntimeError("DB_BACKEND=postgres but POSTGRES_DSN is not set")
        from db_postgres import PostgreSQLAdapter
        return PostgreSQLAdapter(dsn)
    db_path = os.getenv("SQLITE_PATH") or DB_PATH
    create_database(db_path)
    from db import SQLiteAdapter
    return SQLiteAdapter(db_path)


adapter = _build_adapter()

# ── server ─────────────────────────────────────────────────────────────────

_api_key = os.getenv("MCP_API_KEY")
_host = os.getenv("MCP_HOST", "127.0.0.1")
_port = int(os.getenv("MCP_PORT", "8000"))
_base_url = f"http://{_host}:{_port}"

_auth = ApiKeyAuth(_api_key, base_url=_base_url) if _api_key else None
mcp = FastMCP("SQLite Lab MCP Server", auth=_auth, client_log_level="warning")


# ── tools ──────────────────────────────────────────────────────────────────

@mcp.tool(name="search")
def search(
    table: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict:
    """Search rows in a database table.

    Args:
        table: Table name to query.
        columns: Columns to return (default: all).
        filters: Filter list. Each entry: {column, operator (eq|ne|lt|lte|gt|gte|like|in), value}.
        limit: Max rows to return (1-500, default 20).
        offset: Row offset for pagination (default 0).
        order_by: Column to sort by.
        descending: Sort descending when True (default False).

    Returns:
        {table, count, rows, limit, offset}
    """
    try:
        return adapter.search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as e:
        raise ValueError(str(e)) from e


@mcp.tool(name="insert")
def insert(table: str, values: dict) -> dict:
    """Insert a row into a database table.

    Args:
        table: Table to insert into.
        values: Column → value mapping. Must not be empty.

    Returns:
        {table, inserted_id, values}
    """
    try:
        return adapter.insert(table=table, values=values)
    except ValidationError as e:
        raise ValueError(str(e)) from e


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict] | None = None,
    group_by: str | None = None,
) -> dict:
    """Run an aggregate query on a database table.

    Args:
        table: Table to aggregate.
        metric: One of: count, avg, sum, min, max.
        column: Column to aggregate (required for avg/sum/min/max).
        filters: Optional filter list (same format as search).
        group_by: Optional column to group results by.

    Returns:
        {table, metric, column, group_by, rows}
    """
    try:
        return adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    except ValidationError as e:
        raise ValueError(str(e)) from e


# ── resources ─────────────────────────────────────────────────────────────

@mcp.resource("schema://database")
def database_schema() -> str:
    """Full database schema — all tables and their column definitions."""
    tables = adapter.list_tables()
    return json.dumps({t: adapter.get_table_schema(t) for t in tables}, indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Schema for a single table.

    Args:
        table_name: Name of the table to inspect.
    """
    try:
        cols = adapter.get_table_schema(table_name)
        return json.dumps({"table": table_name, "columns": cols}, indent=2)
    except ValidationError as e:
        raise ValueError(str(e)) from e


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite Lab MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=_host,
        help=f"Host for HTTP/SSE transport (default: {_host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_port,
        help=f"Port for HTTP/SSE transport (default: {_port})",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    elif args.transport == "sse":
        if not _api_key:
            print("WARNING: MCP_API_KEY not set — SSE transport has no auth.", file=sys.stderr)
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:  # http / streamable-http
        if not _api_key:
            print("WARNING: MCP_API_KEY not set — HTTP transport has no auth.", file=sys.stderr)
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
