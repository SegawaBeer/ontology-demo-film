"""Moment frames for review/film: every 3 s from 30 to 120, plus every moment of 主时间轴二 第二、三节's tables,
and a contact sheet of all of them. frame=film before 103 s, frame=ending from 103 s.
Usage: film-moments.py [out_dir]"""
import io, os, sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

NEW = 'http://127.0.0.1:5194/frames.html'
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'review', 'film')
TABLE = [86.0, 87.0, 90.0, 91.4, 92.0, 93.8, 95.4, 95.8, 96.0, 98.4, 98.6, 99.0, 101.0, 103.0, 105.0, 105.6, 112.0, 115.0, 116.4, 117.4, 120.0]
TIMES = sorted({round(30 + 3 * i, 1) for i in range(31)} | set(TABLE))
os.makedirs(OUT, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    pages = {}
    for frame in ('film', 'ending'):
        pg = b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto(f'{NEW}?frame={frame}&theme=light&play=0')
        pg.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        pg.evaluate('document.fonts.ready')
        pages[frame] = pg
    tiles = []
    for t in TIMES:
        pg = pages['film' if t < 103 else 'ending']
        pg.evaluate(f'window.__seek({t})'); pg.wait_for_timeout(120)
        im = Image.open(io.BytesIO(pg.screenshot())).convert('RGB')
        im.save(os.path.join(OUT, f't{t:06.2f}.png'))
        tiles.append((t, im.resize((480, 270), Image.LANCZOS)))
        print(t, flush=True)
    b.close()
cols = 7
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new('RGB', (cols * 480, rows * 290), 'white')
d = ImageDraw.Draw(sheet)
for i, (t, im) in enumerate(tiles):
    x, y = (i % cols) * 480, (i // cols) * 290
    sheet.paste(im, (x, y + 20))
    d.text((x + 6, y + 4), f'{t:.1f} s', fill='black')
sheet.save(os.path.join(OUT, '拼版.png'))
print('frames', len(tiles))
