# Database MCP Server — FastMCP + SQLite / PostgreSQL

A FastMCP server that exposes a small relational database through three MCP tools (`search`, `insert`, `aggregate`) and two schema resources. Supports SQLite (default) and PostgreSQL, plus optional Bearer token auth for HTTP/SSE transport.

---

## Project Structure

```
implementation/
  db_base.py        ← shared DatabaseAdapter ABC + validation helpers
  db.py             ← SQLiteAdapter
  db_postgres.py    ← PostgreSQLAdapter
  init_db.py        ← SQLite schema + seed data
  init_pg.py        ← PostgreSQL schema + seed data
  mcp_server.py     ← FastMCP server (tools, resources, auth, transport CLI)
  verify_server.py  ← standalone verification script (39 checks)
  tests/
    test_server.py  ← pytest suite (39 tests, PG tests auto-skip if no DSN)
.env                ← configuration (backend, API key, transport, port)
mcp.json.example    ← Claude Code client config template
```

---

## Prerequisites

- Python 3.11+
- Docker (optional, for PostgreSQL)

---

## Setup

### 1. Install dependencies

```bash
pip install fastmcp psycopg2-binary python-dotenv pytest
```

### 2. Configure `.env`

Copy the defaults — the file already exists at the project root:

```
DB_BACKEND=sqlite          # sqlite or postgres
SQLITE_PATH=               # leave blank → uses implementation/lab.db
POSTGRES_DSN=              # only needed when DB_BACKEND=postgres
MCP_API_KEY=               # set any secret to enable HTTP/SSE auth
MCP_TRANSPORT=stdio        # stdio | http | sse
MCP_HOST=127.0.0.1
MCP_PORT=8001
```

### 3. Initialize the SQLite database

```bash
cd implementation
python init_db.py
# → Database created at: .../implementation/lab.db
```

### 4. Start the MCP server (stdio — default for MCP clients)

```bash
cd implementation
python mcp_server.py
```

---

## Data Model

| Table         | Columns                                           |
|---------------|---------------------------------------------------|
| `students`    | id, name, email, cohort, score                    |
| `courses`     | id, title, credits, department                    |
| `enrollments` | id, student_id, course_id, grade, enrolled_at     |

7 students · 5 courses · 17 enrollments seeded on first run.

---

## Tools

### `search` — query rows with filters, columns, ordering, pagination

```json
{
  "table": "students",
  "filters": [{"column": "cohort", "operator": "eq", "value": "A1"}],
  "columns": ["name", "score"],
  "order_by": "score",
  "descending": true,
  "limit": 10,
  "offset": 0
}
```

Supported operators: `eq` `ne` `lt` `lte` `gt` `gte` `like` `in`  
`limit` is capped at 500. Returns `{table, count, rows, limit, offset}`.

### `insert` — add a row and get back the inserted ID

```json
{
  "table": "students",
  "values": {
    "name": "Gia Khanh",
    "email": "khanh@lab.io",
    "cohort": "A1",
    "score": 95.0
  }
}
```

Returns `{table, inserted_id, values}`.

### `aggregate` — count / avg / sum / min / max with optional grouping

```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

Returns `{table, metric, column, group_by, rows}`.

---

## Resources

| URI                           | Description                       |
|-------------------------------|-----------------------------------|
| `schema://database`           | Full schema for all tables (JSON) |
| `schema://table/{table_name}` | Schema for one table (JSON)       |

---

## Demo Steps

Run each of these to cover every grading checkpoint.

### 1 — Search students in cohort A1

```json
tool: search
{"table": "students", "filters": [{"column": "cohort", "operator": "eq", "value": "A1"}]}
```

Expected: 3 rows (Alice, Bob, Eva).

### 2 — Insert a new student

```json
tool: insert
{"table": "students", "values": {"name": "Demo User", "email": "demo@lab.io", "cohort": "B2", "score": 88.0}}
```

Expected: `{"inserted_id": <n>, "values": {...}}`.

### 3 — Count rows in students

```json
tool: aggregate
{"table": "students", "metric": "count"}
```

### 4 — Average score by cohort

```json
tool: aggregate
{"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"}
```

### 5 — Read the full schema resource

```
resource: schema://database
```

### 6 — Read a single-table schema

```
resource: schema://table/students
```

### 7 — Show a clear error (invalid table)

```json
tool: search
{"table": "ghost_table"}
```

Expected error: `Unknown table: 'ghost_table'`

### 8 — Show a clear error (bad operator)

```json
tool: search
{"table": "students", "filters": [{"column": "cohort", "operator": "regex", "value": "A"}]}
```

Expected error: `Unsupported operator: 'regex'. Allowed: [...]`

---

## Verification

### Standalone script (no MCP transport required)

```bash
cd implementation
python verify_server.py
```

Runs 39 checks: tool discovery, all tool calls, all error cases, auth provider unit test, and live PostgreSQL checks (if `POSTGRES_DSN` is set).

Expected output: `39/39 checks passed`

### pytest suite

```bash
cd implementation
python -m pytest tests/ -v
```

Expected: `39 passed` (9 PostgreSQL tests auto-skip when `POSTGRES_DSN` is blank).

---

## Client Setup

### Claude Code

Copy the config template:

```bash
# Windows
copy mcp.json.example .mcp.json

# macOS / Linux
cp mcp.json.example .mcp.json
```

Or add directly from the CLI:

```bash
claude mcp add sqlite-lab python "C:\Users\giakh\Project\NguyenTrieuGiaKhanh-Day26-Track3-MCP-tool-integration\implementation\mcp_server.py"
```

Once connected, reference resources in your prompt:

```
@sqlite-lab:schema://database
```

### MCP Inspector

```bash
# Windows
npx -y @modelcontextprotocol/inspector ^
  C:\Users\giakh\AppData\Local\Programs\Python\Python311\python.exe ^
  C:\Users\giakh\Project\NguyenTrieuGiaKhanh-Day26-Track3-MCP-tool-integration\implementation\mcp_server.py

# macOS / Linux
npx -y @modelcontextprotocol/inspector python implementation/mcp_server.py
```

Open the Inspector URL in a browser. Use the **Tools** tab to call `search`, `insert`, `aggregate` and the **Resources** tab to read `schema://database`.

### Gemini CLI

```bash
gemini mcp add sqlite-lab \
  C:\Users\giakh\AppData\Local\Programs\Python\Python311\python.exe \
  C:\Users\giakh\Project\NguyenTrieuGiaKhanh-Day26-Track3-MCP-tool-integration\implementation\mcp_server.py \
  --description "SQLite lab FastMCP server" --timeout 10000

gemini mcp list
# → sqlite-lab  Connected

gemini --allowed-mcp-server-names sqlite-lab --yolo \
  -p "Use the sqlite-lab MCP server. Show me the top 3 students by score."
```

---

## Bonus Features

### HTTP / SSE transport with Bearer auth

Set `MCP_API_KEY` in `.env`, then start the server in HTTP mode:

```bash
cd implementation
python mcp_server.py --transport http --port 8001
```

The server requires `Authorization: Bearer <your-key>` on every request. Connect a client with:

```bash
# test auth with curl
curl -s http://127.0.0.1:8001/mcp \
  -H "Authorization: Bearer GiaKhanhKeyIsCool" \
  -H "Content-Type: application/json"
```

Without the header the server returns `401 Unauthorized`.

SSE transport:

```bash
python mcp_server.py --transport sse --port 8001
```

### PostgreSQL backend

Start a PostgreSQL container (or use an existing one):

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres --name postgres-mcp postgres:16
```

Initialize the schema:

```bash
cd implementation
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/labdb python init_pg.py
```

Switch the server to PostgreSQL by updating `.env`:

```
DB_BACKEND=postgres
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/labdb
```

Then start the server normally — the MCP surface (`search`, `insert`, `aggregate`, schema resources) is identical to the SQLite version.

---

## Error Handling Reference

| Bad input                     | Error returned                                          |
|-------------------------------|---------------------------------------------------------|
| Unknown table                 | `Unknown table: 'ghost'`                                |
| Unknown column                | `Unknown column 'ghost' in table 'students'`            |
| Unsupported filter operator   | `Unsupported operator: 'regex'. Allowed: [...]`         |
| SQL-injection table name      | `Invalid table name: 'students; DROP TABLE students--'` |
| Empty insert                  | `'values' must not be empty`                            |
| Unsupported aggregate metric  | `Unsupported metric: 'median'. Allowed: [...]`          |
| avg / sum / min / max without column | `metric 'avg' requires a 'column'`               |

All SQL uses parameterized queries (`?` for SQLite, `%s` for PostgreSQL). No user input is ever concatenated into a SQL string.
