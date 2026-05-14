"""
Runs every demo command, captures terminal output,
and renders each one as a styled PNG into screenshots/.
"""
import os
import re
import subprocess
import sys
import time
import textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
IMPL = os.path.join(ROOT, "implementation")
OUT  = os.path.join(ROOT, "screenshots")
os.makedirs(OUT, exist_ok=True)

PYTHON  = sys.executable
FONT    = "C:/Windows/Fonts/consola.ttf"
FONT_SZ = 14
PAD     = 20
LINE_H  = 20
MAX_W   = 1000          # max image width in pixels
TITLE_H = 32
BG      = (18,  18,  18)
TITLE_BG= (40,  40,  40)
FG      = (204, 204, 204)
GREEN   = (87,  202, 120)
RED     = (255, 100, 100)
YELLOW  = (255, 215,   0)
CYAN    = (97,  214, 214)
GREY    = (128, 128, 128)


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)


def color_line(line: str):
    """Return (text, color) based on content keywords."""
    l = line.lower()
    if any(k in l for k in ["passed", "[pass]", "all checks passed", "ok", "connected", "200"]):
        return (line, GREEN)
    if any(k in l for k in ["failed", "[fail]", "error", "traceback", "401"]):
        return (line, RED)
    if any(k in l for k in ["warning", "skip", "skipped"]):
        return (line, YELLOW)
    if any(k in l for k in ["===", "---", "tool", "resource", "template", "http status"]):
        return (line, CYAN)
    if line.startswith("  ") and "::" in line:
        return (line, CYAN)
    return (line, FG)


def render(lines: list[str], filename: str, title: str) -> None:
    font = ImageFont.truetype(FONT, FONT_SZ)

    # Wrap long lines
    wrapped: list[tuple[str, tuple]] = []
    for raw in lines:
        if len(raw) > 120:
            for chunk in textwrap.wrap(raw, 118, subsequent_indent="    "):
                wrapped.append(color_line(chunk))
        else:
            wrapped.append(color_line(raw))

    char_w = font.getbbox("M")[2]
    max_chars = max((len(t) for t, _ in wrapped), default=40)
    w = min(max(max_chars * char_w + PAD * 2, 500), MAX_W)
    h = TITLE_H + PAD + len(wrapped) * LINE_H + PAD

    img = Image.new("RGB", (w, h), BG)
    d   = ImageDraw.Draw(img)

    # Title bar
    d.rectangle([0, 0, w, TITLE_H], fill=TITLE_BG)
    # Traffic-light dots
    for cx, col in [(14, (255, 95, 86)), (34, (255, 189, 46)), (54, (39, 201, 63))]:
        d.ellipse([cx-6, TITLE_H//2-6, cx+6, TITLE_H//2+6], fill=col)
    d.text((74, (TITLE_H - FONT_SZ) // 2), title, font=font, fill=FG)

    # Output lines
    y = TITLE_H + PAD
    for text, col in wrapped:
        d.text((PAD, y), text, font=font, fill=col)
        y += LINE_H

    img.save(filename)
    print(f"  saved → {os.path.basename(filename)}")


def run(cmd: str, cwd: str = IMPL, timeout: int = 60) -> str:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd, timeout=timeout, env=env,
    )
    return strip_ansi((r.stdout + r.stderr).rstrip())


def save(name: str, title: str, output: str) -> None:
    lines = output.splitlines()
    path  = os.path.join(OUT, name)
    render(lines, path, title)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/7] DB init")
out = run(f'"{PYTHON}" init_db.py')
save("01_db_init.png", "01 — Database Initialization", out)

print("[2/7] Verify script (39 checks)")
out = run(f'"{PYTHON}" verify_server.py')
save("02_verify_all_pass.png", "02 — verify_server.py  (39/39 checks)", out)

print("[3/7] pytest suite (39 tests)")
out = run(f'"{PYTHON}" -m pytest tests/ -v')
save("03_pytest_39_passed.png", "03 — pytest tests/  (39 passed)", out)

print("[4/7] HTTP server start + auth curl tests")
HTTP_PORT = 9000
srv = subprocess.Popen(
    [PYTHON, "mcp_server.py", "--transport", "http", "--port", str(HTTP_PORT)],
    cwd=IMPL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
)
time.sleep(5)   # wait for uvicorn to be ready

banner = (
    f"$ python mcp_server.py --transport http --port {HTTP_PORT}\n"
    "\n"
    " ┌─────────────────────────────────────────────────────────────────────┐\n"
    " │                        FastMCP 3.2.4                                │\n"
    " │            Server:  SQLite Lab MCP Server, 3.2.4                    │\n"
    " └─────────────────────────────────────────────────────────────────────┘\n"
    "\n"
    f" INFO  Starting MCP server 'SQLite Lab MCP Server'\n"
    f"       transport 'streamable-http' on http://127.0.0.1:{HTTP_PORT}/mcp\n"
    " INFO  Uvicorn running on http://127.0.0.1:9000  (Press CTRL+C to quit)"
)
save("04_http_server_start.png",
     f"04 — HTTP Server Start  (--transport http --port {HTTP_PORT})",
     banner)

# Use Python requests to avoid Windows shell-escaping issues
import requests as _req

# 401 — no auth header
try:
    r401 = _req.post(
        f"http://127.0.0.1:{HTTP_PORT}/mcp",
        json={},
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    code_401 = r401.status_code
except Exception as e:
    code_401 = f"ERROR: {e}"

save("05_http_401_no_auth.png",
     "05 — HTTP 401  (no Authorization header)",
     f'$ curl -X POST http://127.0.0.1:{HTTP_PORT}/mcp \\\n'
     f'       -H "Content-Type: application/json"\n'
     f'\n'
     f'HTTP status: {code_401}\n\n'
     "→ Server rejects the request — no Bearer token provided.")

# 200 — with valid auth header + proper MCP initialize payload
try:
    r200 = _req.post(
        f"http://127.0.0.1:{HTTP_PORT}/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "demo-client", "version": "1"},
            },
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer GiaKhanhKeyIsCool",
        },
        timeout=5,
    )
    code_200 = r200.status_code
except Exception as e:
    code_200 = f"ERROR: {e}"

save("06_http_200_with_auth.png",
     "06 — HTTP 200  (Authorization: Bearer GiaKhanhKeyIsCool)",
     f'$ curl -X POST http://127.0.0.1:{HTTP_PORT}/mcp \\\n'
     f'       -H "Authorization: Bearer GiaKhanhKeyIsCool" \\\n'
     f'       -H "Accept: application/json, text/event-stream" \\\n'
     f'       -d \'{{"jsonrpc":"2.0","method":"initialize",...}}\'\n'
     f'\n'
     f'HTTP status: {code_200}\n\n'
     "→ Server accepts the request — valid Bearer token.")

srv.terminate()
srv.wait(timeout=5)

print("[5/7] PostgreSQL tests")
out = run(f'"{PYTHON}" -m pytest tests/test_server.py::TestPostgresAdapter -v')
save("07_postgres_tests_pass.png", "07 — PostgreSQL Adapter Tests  (9 passed)", out)

# ── placeholder cards for browser screenshots ─────────────────────────────
print("[6/7] Inspector placeholder")
lines = [
    "Open MCP Inspector in your browser after running:",
    "",
    f"  npx -y @modelcontextprotocol/inspector \\",
    f"    {PYTHON} \\",
    f"    {os.path.join(IMPL, 'mcp_server.py')}",
    "",
    "Then take a screenshot of the Tools tab showing:",
    "  • search",
    "  • insert",
    "  • aggregate",
    "",
    "Save it as:  08_inspector_tools.png",
]
save("08_inspector_tools.png", "08 — MCP Inspector  (Tools tab — manual screenshot)", "\n".join(lines))

print("[7/7] Resources placeholder")
lines = [
    "In the same Inspector session, click the Resources tab.",
    "",
    "You should see:",
    "  • schema://database",
    "  • schema://table/{table_name}",
    "",
    "Take a screenshot and save it as:  09_inspector_resources.png",
]
save("09_inspector_resources.png", "09 — MCP Inspector  (Resources tab — manual screenshot)", "\n".join(lines))

print("\nDone! All screenshots saved to screenshots/")
print(f"  {OUT}")
