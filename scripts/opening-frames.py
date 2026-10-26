"""Render the review stills, sheets and the reveal curve for opening milestone one."""
import csv, os, time
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
OUT = f'{ROOT}/review/opening'
URL = 'http://127.0.0.1:5192/frames.html'
os.makedirs(OUT, exist_ok=True)
TIMES = ['0.6', '3', '5.5', '5.8', '6.1', '6.4', '7.0', '7.30', '7.45', '7.60', '8.0', '8.6', '9.05', '9.6']

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)

    def shot(query, path):
        page.goto(f'{URL}?{query}')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        time.sleep(0.5)
        page.screenshot(path=path)
        return path

    for t in TIMES:
        shot(f'frame=opening&theme=light&t={t}', f'{OUT}/t{float(t):05.2f}.png')
    shot('frame=opening&theme=light&t=7.3&mask=1', f'{OUT}/mask-07.30.png')
    shot('frame=opening&theme=light&t=6.4&mask=disk-solid', f'{OUT}/disk-solid-06.40.png')

    # Blade close-up across the hand-off.
    page.goto(f'{URL}?frame=opening&theme=light&t=7.45')
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    box = page.evaluate('window.__openingProbe().fadeBox')
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    strip = Image.new('RGB', (4 * 360, 280), '#ffffff')
    for i, t in enumerate(('7.30', '7.45', '7.60', '7.65')):
        p = shot(f'frame=opening&theme=light&t={t}', f'/tmp/zoom-{t}.png')
        im = Image.open(p).convert('RGB').crop((int(cx) - 90, int(cy) - 70, int(cx) + 90, int(cy) + 70))
        strip.paste(im.resize((360, 280), Image.LANCZOS), (i * 360, 0))
    strip.save(f'{OUT}/换叶片放大.png')

    # Disc appearance, every 0.2 s.
    grid = Image.new('RGB', (5 * 320, 2 * 270), '#ffffff')
    disc_times = [round(5.0 + i * 0.2, 1) for i in range(10)]
    for i, t in enumerate(disc_times):
        p = shot(f'frame=opening&theme=light&t={t}', f'/tmp/disc-{t}.png')
        im = Image.open(p).convert('RGB').crop((0, 0, 1280, 1080)).resize((320, 270), Image.LANCZOS)
        grid.paste(im, ((i % 5) * 320, (i // 5) * 270))
    grid.save(f'{OUT}/涡轮盘出现.png')
    browser.close()

files = [f'{OUT}/t{float(t):05.2f}.png' for t in TIMES] + [f'{OUT}/mask-07.30.png', f'{OUT}/disk-solid-06.40.png']
sheet = Image.new('RGB', (1920, 1080), '#ffffff')
for i, path in enumerate(files):
    sheet.paste(Image.open(path).convert('RGB').resize((480, 270), Image.LANCZOS), ((i % 4) * 480, (i // 4) * 270))
sheet.save(f'{OUT}/拼版.png')

# Reveal curve.
rows = []
with open(f'{OUT}/涡轮盘铺材质曲线.csv') as f:
    for row in csv.DictReader(f):
        rows.append((float(row['t']), float(row['S/F'])))
chart = Image.new('RGB', (960, 540), '#ffffff')
d = ImageDraw.Draw(chart)
font = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 16)
left, top, w, h = 70, 40, 840, 440
d.rectangle([left, top, left + w, top + h], outline='#c8ccc8')
d.text((left, 12), '涡轮盘已铺材质的比例（S/F）随时间', font=font, fill='#1c2228')
for k in range(0, 101, 25):
    y = top + h - h * k / 100
    d.line([left, y, left + w, y], fill='#e6e8e6')
    d.text((left - 44, y - 8), f'{k}%', font=font, fill='#5b646b')
for t0 in (4.8, 5.6, 6.0, 6.4, 6.8, 7.0):
    x = left + w * (t0 - 4.8) / 2.4
    d.text((x - 12, top + h + 8), f'{t0:.1f}s', font=font, fill='#5b646b')
if rows:
    points = [(left + w * (t0 - 4.8) / 2.4, top + h - h * v) for t0, v in rows]
    d.line(points, fill='#1c5fb8', width=2)
chart.save(f'{OUT}/涡轮盘铺材质曲线.png')
print('deliverables written', len(files), 'tiles')
