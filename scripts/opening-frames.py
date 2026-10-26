"""Render the review stills and the contact sheet for opening milestone one."""
import os, time
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
OUT = f'{ROOT}/review/opening'
URL = 'http://127.0.0.1:5192/frames.html'
os.makedirs(OUT, exist_ok=True)

TIMES = ['0.6', '3', '5.5', '6.4', '7.0', '7.39', '7.40', '8.0', '8.6', '9.05', '9.6']
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    for t in TIMES:
        page.goto(f'{URL}?frame=opening&theme=light&t={t}')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        time.sleep(0.5)
        page.screenshot(path=f'{OUT}/t{float(t):05.2f}.png')
    page.goto(f'{URL}?frame=opening&theme=light&t=7.3&mask=1')
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    time.sleep(0.5)
    page.screenshot(path=f'{OUT}/mask-07.30.png')
    browser.close()

files = [f'{OUT}/t{float(t):05.2f}.png' for t in TIMES] + [f'{OUT}/mask-07.30.png']
sheet = Image.new('RGB', (1920, 810), '#ffffff')
for i, path in enumerate(files):
    im = Image.open(path).convert('RGB').resize((480, 270), Image.LANCZOS)
    sheet.paste(im, ((i % 4) * 480, (i // 4) * 270))
sheet.save(f'{OUT}/拼版.png')
print('sheet written', len(files), 'tiles')
