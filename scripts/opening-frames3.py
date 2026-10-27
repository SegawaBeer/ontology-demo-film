"""Render the milestone three A stills, sheets and curves."""
import json, os, time
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
OUT = f'{ROOT}/review/opening/m3'
URL = 'http://127.0.0.1:5192/frames.html'
BG = (238, 240, 238)
os.makedirs(OUT, exist_ok=True)
TIMES = ['17.0', '17.4', '17.8', '18.3', '18.7', '19.2', '19.6', '20.2', '20.6', '21.0', '21.3', '21.6', '22.0', '22.4', '23.0']
PIECES = [
    ('combustor', ['combustor.cans', 'combustor.casing', 'combustor.injectors', 'combustor.inner-shell'], 17.00, 0.20, 0.60),
    ('core', ['core-casing.bolts', 'core-casing.drum', 'core-casing.inner-wall', 'core-casing.tiles', 'turbine.band', 'turbine.inner-cone'], 17.80, 0.20, 0.70),
    ('fanhub', ['fan.hub', 'fan.inner-shroud'], 18.70, 0.15, 0.55),
    ('cowl', ['fan-cowl.aft', 'fan-cowl.lip', 'fan-cowl.shell'], 20.20, 0.20, 0.90),
    ('nacelle', ['nacelle.duct'], 20.20, 0.20, 0.90),
    ('exhaust', ['exhaust.bolts', 'exhaust.fittings', 'exhaust.nozzle', 'exhaust.tail-cone'], 21.30, 0.15, 0.60),
    ('spinner', ['fan.spinner'], 21.30, 0.15, 0.60),
]
FAN = 'fan.blades'

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    helper = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)

    def shot(query, path):
        page.goto(f'{URL}?{query}')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.4)
        page.screenshot(path=path)
        return path

    for t in TIMES:
        shot(f'frame=opening&theme=light&t={t}', f'{OUT}/t{float(t):05.2f}.png')
    shot('frame=opening&theme=light&t=23.0&mask=1', f'{OUT}/mask-23.00.png')

    files = [f'{OUT}/t{float(t):05.2f}.png' for t in TIMES] + [f'{OUT}/mask-23.00.png']
    sheet = Image.new('RGB', (1920, 1080), '#ffffff')
    for i, path in enumerate(files):
        sheet.paste(Image.open(path).convert('RGB').resize((480, 270), Image.LANCZOS), ((i % 4) * 480, (i // 4) * 270))
    sheet.save(f'{OUT}/拼版.png')

    # Outline close-ups: outline instant, one third, two thirds, finished.
    def centre(ids, t):
        helper.goto(f'{URL}?frame=opening&theme=light&mask=part:{ids}&t={t}')
        helper.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.25)
        helper.screenshot(path='/tmp/c3.png')
        im = Image.open('/tmp/c3.png').convert('RGB').load()
        xs = [x for y in range(100, 1080, 2) for x in range(0, 1280, 2) if max(im[x, y]) < 245]
        ys = [y for y in range(100, 1080, 2) for x in range(0, 1280, 2) if max(im[x, y]) < 245]
        return (sum(xs) // len(xs), sum(ys) // len(ys)) if xs else (640, 540)

    rows = PIECES[:4] + [PIECES[5]] + [(FAN, [FAN], 19.10, 0.12, 0.12 * 16)]
    zoom = Image.new('RGB', (4 * 480, 6 * 360), '#ffffff')
    for r, (name, ids, start, o0, sweep) in enumerate(rows):
        key = ",".join(ids)
        moments = [start + o0 * 0.5, start + o0 + (sweep - o0) / 3, start + o0 + 2 * (sweep - o0) / 3, start + sweep + 0.05]
        for c, t in enumerate(moments):
            cx, cy = centre(key, t)
            path = shot(f'frame=opening&theme=light&t={t:.3f}', f'/tmp/z3-{r}-{c}.png')
            im = Image.open(path).convert('RGB').crop((cx - 240, cy - 180, cx + 240, cy + 180))
            zoom.paste(im, (c * 480, r * 360))
    zoom.save(f'{OUT}/线框阶段放大.png')

    # Graph column at three moments.
    grapher = Image.new('RGB', (1920, 1080), '#ffffff')
    for i, t in enumerate(('17.0', '20.2', '22.35')):
        p = shot(f'frame=opening&theme=light&t={t}', f'/tmp/g3-{i}.png')
        grapher.paste(Image.open(p).convert('RGB').crop((1280, 0, 1920, 1080)), (i * 640, 0))
    grapher.save(f'{OUT}/连线.png')

    # Reveal curves at 10 fps: G from the no-lines picture, O from lines minus no-lines.
    curves = {}
    for name, ids, start, o0, sweep in PIECES:
        key = ",".join(ids)
        helper.goto(f'{URL}?frame=opening&theme=light&mask=part:{key}&t={start}')
        helper.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        series = []
        for k in range(int((sweep + 0.1) * 10) + 1):
            tt = start - 0.05 + k / 10
            page.goto(f'{URL}?frame=opening&theme=light&solo={key}&t={tt:.2f}')
            page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
            page.screenshot(path='/tmp/cg-on.png')
            helper.goto(f'{URL}?frame=opening&theme=light&mask=part:{key}&t={tt:.2f}')
            helper.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
            helper.screenshot(path='/tmp/cg-mask.png')
            pa = Image.open('/tmp/cg-on.png').convert('RGB').load()
            pm = Image.open('/tmp/cg-mask.png').convert('RGB').load()
            pts = [(x, y) for y in range(100, 1080, 4) for x in range(0, 1280, 4) if max(pm[x, y]) < 245]
            if not pts:
                continue
            g = sum(1 for (x, y) in pts
                    if max(abs(pa[x, y][i] - BG[i]) for i in range(3)) > 40) / len(pts)
            series.append([round(tt, 2), round(g, 3)])
        curves[name] = series
    browser.close()

with open(f'{OUT}/m3-curves.json', 'w') as f:
    json.dump(curves, f)

chart = Image.new('RGB', (1100, 620), '#ffffff')
d = ImageDraw.Draw(chart)
font = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 15)
d.text((70, 14), '每件零件铺材质的推进（0 = 只有线框，1 = 铺满）', font=font, fill='#1c2228')
left, top, w, h = 70, 50, 960, 500
d.rectangle([left, top, left + w, top + h], outline='#c8ccc8')
for k in range(0, 101, 25):
    y = top + h - h * k / 100
    d.line([left, y, left + w, y], fill='#e6e8e6')
    d.text((left - 44, y - 8), f'{k}%', font=font, fill='#5b646b')
colours = ['#1c5fb8', '#c2571a', '#2f7d4f', '#7a4fa3', '#a8342a', '#0f7d8c', '#8a5a00']
for i, (name, series) in enumerate(curves.items()):
    if not series:
        continue
    t0 = series[0][0]
    pts = [(left + w * (v[0] - t0) / 1.0, top + h - h * v[1]) for v in series]
    d.line(pts, fill=colours[i % len(colours)], width=2)
    d.text((left + 10, top + 10 + i * 18), name, font=font, fill=colours[i % len(colours)])
chart.save(f'{OUT}/线框到材质曲线.png')
print('m3 deliverables written')
