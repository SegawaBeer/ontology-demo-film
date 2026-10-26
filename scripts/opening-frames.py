"""Render the review stills, sheets and the reveal curve for opening milestone one."""
import csv, json, os, time
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
OUT = f'{ROOT}/review/opening'
URL = 'http://127.0.0.1:5192/frames.html'
os.makedirs(OUT, exist_ok=True)
TIMES = ['0.6', '3', '5.5', '5.8', '6.1', '6.4', '7.0', '7.30', '7.45', '7.60', '8.0', '8.6', '9.05', '9.6']
M2 = ['10.1', '10.7', '11.3', '11.9', '12.6', '13.2', '13.5', '14.5', '15.5', '16.3', '17.0']

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
    os.makedirs(f'{OUT}/m2', exist_ok=True)
    for t in M2:
        shot(f'frame=opening&theme=light&t={t}', f'{OUT}/m2/t{float(t):05.2f}.png')
    shot('frame=opening&theme=light&t=17.0&mask=1', f'{OUT}/m2/mask-17.00.png')
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
    # Outline phase close-ups: stage two and the compressor stage-four ring.
    def part_centre(ids, t):
        page.goto(f'{URL}?frame=opening&theme=light&mask=part:{ids}&t={t}')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        time.sleep(0.3)
        page.screenshot(path='/tmp/oc.png')
        im = Image.open('/tmp/oc.png').convert('L').load()
        xs = [x for y in range(0, 1080, 2) for x in range(0, 1280, 2) if im[x, y] < 60]
        ys = [y for y in range(0, 1080, 2) for x in range(0, 1280, 2) if im[x, y] < 60]
        return (sum(xs) // len(xs), sum(ys) // len(ys)) if xs else (640, 540)

    zoom = Image.new('RGB', (4 * 480, 3 * 360), '#ffffff')
    rows = [('turbine.stage-2-blades,turbine.stage-2-hub,turbine.stage-2-outer,turbine.stage-2-tip-ring,turbine.stage-1-outer,turbine.stage-1-tip-ring', [10.15, 10.25, 10.40, 10.60]),
            ('compressor.stage-4', [13.54, 13.61, 13.75, 13.90]),
            ('compressor.stators', [13.54 + 0.0, 13.61, 13.75, 13.90])]
    for r, row in enumerate(rows):
        ids, times = row[0], row[1]
        for c, t in enumerate(times):
            cx, cy = part_centre(ids, t)
            pth = shot(f'frame=opening&theme=light&t={t}', f'/tmp/oz-{r}-{c}.png')
            im = Image.open(pth).convert('RGB').crop((cx - 240, cy - 180, cx + 240, cy + 180))
            zoom.paste(im, (c * 480, r * 360))
    zoom.save(f'{OUT}/m2/线框阶段放大.png')

    # Graph column at 9.6 and 17.0.
    a = Image.open(shot('frame=opening&theme=light&t=9.6', '/tmp/g1.png')).convert('RGB').crop((1280, 0, 1920, 1080))
    c = Image.open(shot('frame=opening&theme=light&t=17.0', '/tmp/g2.png')).convert('RGB').crop((1280, 0, 1920, 1080))
    line_sheet = Image.new('RGB', (1280, 1080), '#ffffff')
    line_sheet.paste(a, (0, 0)); line_sheet.paste(c, (640, 0))
    line_sheet.save(f'{OUT}/m2/连线.png')

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
# Milestone two sheet: 11 stills plus the 17 s mask, 4 columns by 3 rows.
m2_files = [f'{OUT}/m2/t{float(t):05.2f}.png' for t in M2] + [f'{OUT}/m2/mask-17.00.png']
m2_sheet = Image.new('RGB', (1920, 810), '#ffffff')
for i, path in enumerate(m2_files):
    m2_sheet.paste(Image.open(path).convert('RGB').resize((480, 270), Image.LANCZOS), ((i % 4) * 480, (i // 4) * 270))
m2_sheet.save(f'{OUT}/m2/拼版.png')

# Reveal curves for the milestone two pieces.
try:
    curves = json.load(open(f'{OUT}/m2-curves.json'))
except Exception:
    curves = {}
chart2 = Image.new('RGB', (1100, 620), '#ffffff')
d2 = ImageDraw.Draw(chart2)
font2 = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 15)
d2.text((70, 14), '每类零件从线框到材质的推进（0 = 只有线框，1 = 铺满）', font=font2, fill='#1c2228')
left2, top2, w2, h2 = 70, 50, 960, 500
d2.rectangle([left2, top2, left2 + w2, top2 + h2], outline='#c8ccc8')
for k in range(0, 101, 25):
    y = top2 + h2 - h2 * k / 100
    d2.line([left2, y, left2 + w2, y], fill='#e6e8e6')
    d2.text((left2 - 44, y - 8), f'{k}%', font=font2, fill='#5b646b')
colours = ['#1c5fb8', '#c2571a', '#2f7d4f', '#7a4fa3', '#a8342a', '#0f7d8c', '#8a5a00', '#3b6d11']
for i, (name, series) in enumerate(curves.items()):
    if not series:
        continue
    t0 = series[0][0]
    pts = [(left2 + w2 * (v[0] - t0) / 0.9, top2 + h2 - h2 * v[1]) for v in series]
    d2.line(pts, fill=colours[i % len(colours)], width=2)
    d2.text((left2 + 10, top2 + 10 + i * 18), name, font=font2, fill=colours[i % len(colours)])
chart2.save(f'{OUT}/m2/线框到材质曲线.png')

print('deliverables written', len(files), 'tiles + m2')
