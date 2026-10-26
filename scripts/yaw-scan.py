"""Ask the open frame for its 72 yaw candidates and write them to a CSV.

Usage: yaw-scan.py URL OUT.csv
"""
import csv, json, sys, time
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
if 'scan=1' not in url:
    url += '&scan=1'
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    logs = []
    page.on('console', lambda m: logs.append(f'{m.type}: {m.text}'))
    page.on('pageerror', lambda e: logs.append(f'pageerror: {e}'))
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    time.sleep(0.5)
    data = page.evaluate('window.__openScan()')
    b.close()

rows = data['candidates']
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['yaw', 'A', 'B', 'R', 'R0', 'R5'])
    w.writeheader()
    w.writerows(rows)
print(json.dumps({'chosen': data['chosen'], 'okCount': data['okCount']}))
for l in logs[-10:]:
    print(l)
