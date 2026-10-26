"""Render a few clip moments to PNG for review. Usage: shot-times.py URL OUTDIR t1 t2 ..."""
import sys, time
from playwright.sync_api import sync_playwright
url, outdir, times = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3:]]
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    logs = []
    page.on('console', lambda m: logs.append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
    page.on('pageerror', lambda e: logs.append(f'pageerror: {e}'))
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=90000)
    for t in times:
        page.evaluate(f"window.__seek({t})")
        time.sleep(0.25)
        page.screenshot(path=f"{outdir}/t{t:05.2f}.png")
    b.close()
    for l in logs[-15:]: print(l)
