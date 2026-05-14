import os, sys, time
from playwright.sync_api import sync_playwright

TOKEN = "a05b525df75edf61e2e77e86502d801c6afbe95a8c612074ba85f62955f0fe79"
URL   = f"http://localhost:7100/?MCP_PROXY_PORT=7101&MCP_PROXY_AUTH_TOKEN={TOKEN}"
OUT   = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    print("Opening Inspector...")
    page.goto(URL, wait_until="networkidle", timeout=15000)
    time.sleep(2)

    # Click Connect button
    print("Connecting...")
    connect_btn = page.locator("button", has_text="Connect")
    connect_btn.wait_for(timeout=8000)
    connect_btn.click()
    time.sleep(3)

    # ── Tools tab ──────────────────────────────────────────────────────────
    print("Navigating to Tools tab...")
    page.locator("button", has_text="Tools").first.click()
    time.sleep(1)
    # Click "List Tools" to populate the tool list
    page.locator("button", has_text="List Tools").click()
    time.sleep(2)

    path_tools = os.path.join(OUT, "08_inspector_tools.png")
    page.screenshot(path=path_tools, full_page=False)
    print(f"  saved → 08_inspector_tools.png")

    # ── Resources tab ──────────────────────────────────────────────────────
    print("Navigating to Resources tab...")
    page.locator("button", has_text="Resources").first.click()
    time.sleep(1)
    # Click "List Resources" and "List Templates"
    page.locator("button", has_text="List Resources").click()
    time.sleep(1)
    page.locator("button", has_text="List Templates").click()
    time.sleep(2)

    path_res = os.path.join(OUT, "09_inspector_resources.png")
    page.screenshot(path=path_res, full_page=False)
    print(f"  saved → 09_inspector_resources.png")

    browser.close()

print("\nDone!")
