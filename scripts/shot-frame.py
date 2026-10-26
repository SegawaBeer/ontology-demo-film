import sys, time
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    logs = []
    page.on('console', lambda m: logs.append(f'{m.type}: {m.text}'))
    page.on('pageerror', lambda e: logs.append(f'pageerror: {e}'))
    page.goto(url)
    try:
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000)
    except Exception as e:
        logs.append(f'timeout: {e}')
    time.sleep(0.8)
    page.screenshot(path=out)
    b.close()
    for l in logs[-20:]: print(l)
