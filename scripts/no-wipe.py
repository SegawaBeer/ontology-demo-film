"""Side by side of the depth shells before and after the render order fix.

Rows are the four moments the supervisor named, left is the commit before the
fix (1e5dc12), right is the current build. Both are the left column at 1:2.
"""
import os
import time
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

NOW = 'http://127.0.0.1:5192/frames.html'
BEFORE = 'http://127.0.0.1:5291/frames.html'
PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
OUT = os.path.join(PROJECT_ROOT, 'review/opening/m3')
TIMES = ['17.85', '20.30', '12.78', '13.54']
W, H = 640, 540

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)

    def shot(url, t, path):
        page.goto(f'{url}?frame=opening&theme=light&t={t}')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.3)
        page.screenshot(path=path)
        return Image.open(path).convert('RGB').crop((0, 0, 1280, 1080)).resize((W, H), Image.LANCZOS)

    sheet = Image.new('RGB', (2 * W, len(TIMES) * H), '#ffffff')
    for r, t in enumerate(TIMES):
        sheet.paste(shot(BEFORE, t, f'/tmp/nw-before-{t}.png'), (0, r * H))
        sheet.paste(shot(NOW, t, f'/tmp/nw-now-{t}.png'), (W, r * H))
    browser.close()

d = ImageDraw.Draw(sheet)
font = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 17)
for r, t in enumerate(TIMES):
    d.rectangle([0, r * H, 2 * W, r * H + 26], fill='#eef0ee')
    d.text((10, r * H + 5), f'{t} 秒  改前（1e5dc12）', font=font, fill='#1c2228')
    d.text((W + 10, r * H + 5), f'{t} 秒  改后', font=font, fill='#1c2228')
sheet.save(f'{OUT}/不擦掉金属.png')
print('written')
