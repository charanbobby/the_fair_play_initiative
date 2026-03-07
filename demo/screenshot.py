"""Capture Iteration HTML files as high-res PNGs for Canva import.

Usage:
  uv run --with playwright python demo/screenshot.py
  (first time only: uv run --with playwright playwright install chromium)
"""

import pathlib, sys
from playwright.sync_api import sync_playwright

DEMO_DIR = pathlib.Path(__file__).parent
FILES = list(DEMO_DIR.glob("Iteration-*.html"))

if not FILES:
    print("No Iteration-*.html files found in demo/")
    sys.exit(1)

with sync_playwright() as p:
    browser = p.chromium.launch()
    for html_file in sorted(FILES):
        page = browser.new_page(device_scale_factor=2)  # 2x for retina-crisp
        page.goto(html_file.as_uri())
        page.wait_for_load_state("networkidle")

        # screenshot the <body> element only (no extra whitespace)
        body = page.locator("body")
        out = html_file.with_suffix(".png")
        body.screenshot(path=str(out))
        print(f"✓ {out.name}  ({out.stat().st_size // 1024} KB)")

    browser.close()

print(f"\nDone — PNGs saved in {DEMO_DIR}")
