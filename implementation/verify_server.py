"""
Standalone verification script — runs without a live MCP transport.
Covers: tool discovery, all successful calls, all error cases,
backend selection (SQLite + PostgreSQL if POSTGRES_DSN is set),
and HTTP auth token verification.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from init_db import create_database, DB_PATH
from db import SQLiteAdapter
from db_base import ValidationError

create_database(DB_PATH)
adapter = SQLiteAdapter(DB_PATH)

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label: str, fn):
    try:
        result = fn()
        snippet = ""
        if result is not None:
            snippet = " => " + json.dumps(result)[:120]
        print(f"  [{PASS}] {label}{snippet}")
        results.append((label, True))
    except Exception as e:
        print(f"  [{FAIL}] {label} => ERROR: {e}")
        results.append((label, False))


def check_raises(label: str, fn):
    try:
        fn()
        print(f"  [{FAIL}] {label}  (expected error, got success)")
        results.append((label, False))
    except (ValidationError, ValueError) as e:
        print(f"  [{PASS}] {label}  => {e}")
        results.append((label, True))


async def discover_tools():
    from mcp_server import mcp
    tools = await mcp.list_tools()
    resources = await mcp.list_resources()
    templates = await mcp.list_resource_templates()
    return (
        [t.name for t in tools],
        [str(r.uri) for r in resources],
        [t.uri_template for t in templates],
    )


# ══════════════════════════════════════════════════════════════════════════
print("\n=== Tool Discovery ===")
tool_names, resource_uris, template_uris = asyncio.run(discover_tools())

for name in ("search", "insert", "aggregate"):
    check(f"{name} tool registered",
          lambda n=name: n in tool_names or (_ for _ in ()).throw(AssertionError(f"{n} not in {tool_names}")))

print(f"  Tools:     {tool_names}")
print(f"  Resources: {resource_uris}")
print(f"  Templates: {template_uris}")


# ══════════════════════════════════════════════════════════════════════════
print("\n=== Successful Tool Calls ===")
check("search all students",
      lambda: adapter.search("students"))

check("search cohort A1",
      lambda: adapter.search("students",
                              filters=[{"column": "cohort", "operator": "eq", "value": "A1"}]))

check("search columns + order_by desc",
      lambda: adapter.search("students",
                              columns=["name", "score"],
                              order_by="score",
                              descending=True,
                              limit=3))

check("search pagination offset=2",
      lambda: adapter.search("students", limit=2, offset=2))

check("search operator gte",
      lambda: adapter.search("students",
                              filters=[{"column": "score", "operator": "gte", "value": 90}]))

check("search operator like",
      lambda: adapter.search("students",
                              filters=[{"column": "name", "operator": "like", "value": "A%"}]))

check("search operator in",
      lambda: adapter.search("students",
                              filters=[{"column": "cohort", "operator": "in", "value": ["A1", "B2"]}]))

check("insert new student",
      lambda: adapter.insert("students", {
          "name": "Verify Student",
          "email": f"verify_{int(time.time()*1000)}@lab.io",
          "cohort": "Z9",
          "score": 55.0,
      }))

check("aggregate count(*)",
      lambda: adapter.aggregate("students", "count"))

check("aggregate avg score",
      lambda: adapter.aggregate("students", "avg", column="score"))

check("aggregate sum credits",
      lambda: adapter.aggregate("courses", "sum", column="credits"))

check("aggregate min score",
      lambda: adapter.aggregate("students", "min", column="score"))

check("aggregate max score",
      lambda: adapter.aggregate("students", "max", column="score"))

check("aggregate count group_by cohort",
      lambda: adapter.aggregate("students", "count", group_by="cohort"))

check("aggregate avg with filter",
      lambda: adapter.aggregate("students", "avg", column="score",
                                 filters=[{"column": "cohort", "operator": "eq", "value": "A1"}]))

check("schema resource — all tables",
      lambda: json.loads(__import__("mcp_server").database_schema()))

check("schema resource — students table",
      lambda: json.loads(__import__("mcp_server").table_schema("students")))


# ══════════════════════════════════════════════════════════════════════════
print("\n=== Error Cases ===")
check_raises("search unknown table",
             lambda: adapter.search("nonexistent"))

check_raises("search unknown column",
             lambda: adapter.search("students", columns=["ghost"]))

check_raises("search unsupported operator",
             lambda: adapter.search("students",
                                    filters=[{"column": "cohort", "operator": "regex", "value": "A"}]))

check_raises("search SQL-injection identifier",
             lambda: adapter.search("students; DROP TABLE students--"))

check_raises("insert empty values",
             lambda: adapter.insert("students", {}))

check_raises("insert unknown column",
             lambda: adapter.insert("students", {"ghost": "x", "email": "x@x.io", "name": "X", "cohort": "X"}))

check_raises("insert unknown table",
             lambda: adapter.insert("ghost", {"name": "x"}))

check_raises("aggregate unsupported metric",
             lambda: adapter.aggregate("students", "median"))

check_raises("aggregate avg without column",
             lambda: adapter.aggregate("students", "avg"))

check_raises("aggregate unknown table",
             lambda: adapter.aggregate("ghost", "count"))

check_raises("table schema unknown table",
             lambda: adapter.get_table_schema("nonexistent"))


# ══════════════════════════════════════════════════════════════════════════
print("\n=== Auth Provider (unit test) ===")

async def _verify_auth():
    from mcp_server import ApiKeyAuth
    auth = ApiKeyAuth("secret-key-123", base_url="http://127.0.0.1:8000")

    good = await auth.verify_token("secret-key-123")
    bad = await auth.verify_token("wrong-key")
    return good, bad

good_tok, bad_tok = asyncio.run(_verify_auth())
check("valid API key returns AccessToken",   lambda: good_tok is not None or (_ for _ in ()).throw(AssertionError("expected token")))
check("invalid API key returns None",        lambda: bad_tok is None or (_ for _ in ()).throw(AssertionError("expected None")))


# ══════════════════════════════════════════════════════════════════════════
print("\n=== PostgreSQL Adapter (skipped if POSTGRES_DSN not set) ===")
pg_dsn = os.getenv("POSTGRES_DSN", "")
if not pg_dsn:
    print("  [SKIP] POSTGRES_DSN not set — skipping PG checks")
else:
    try:
        from init_pg import init_postgres
        init_postgres(pg_dsn)  # ensure schema + seed exist

        from db_postgres import PostgreSQLAdapter
        pg = PostgreSQLAdapter(pg_dsn)

        check("PG list_tables",  lambda: pg.list_tables())
        check("PG search",       lambda: pg.search("students"))
        check("PG insert",       lambda: pg.insert("students", {
            "name": "PG Verify",
            "email": f"pgverify_{int(time.time()*1000)}@lab.io",
            "cohort": "Z9",
            "score": 75.0,
        }))
        check("PG aggregate count", lambda: pg.aggregate("students", "count"))
        check("PG aggregate avg",   lambda: pg.aggregate("students", "avg", column="score"))
        check_raises("PG unknown table", lambda: pg.search("ghost"))
    except Exception as e:
        print(f"  [FAIL] PostgreSQL setup failed: {e}")
        results.append(("PostgreSQL adapter", False))


# ══════════════════════════════════════════════════════════════════════════
print("\n=== Summary ===")
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"  {passed}/{total} checks passed")
if passed < total:
    print("  FAILED:")
    for label, ok in results:
        if not ok:
            print(f"    - {label}")
    sys.exit(1)
else:
    print("  All checks passed.")
