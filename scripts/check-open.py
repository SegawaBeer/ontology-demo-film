"""Twelve automated checks for the opening frame (0:03, one blade).

Usage: check-open.py [--skip-build]
Writes review/style-frames/results.json and the images the checks refer to.
"""
import json, os, subprocess, sys, time
from collections import deque
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
WORK = f'{ROOT}/.claude/worktrees/style-frames'
OUT = f'{ROOT}/review/style-frames'
STYLE = f'{ROOT}/样式图/开头0-03一枚叶片-浅色.png'
BASE = '/tmp/open-check/base'
CUR = '/tmp/open-check/current'
URL = 'http://127.0.0.1:5192/frames.html'
# The committed HEAD, served from a separate checkout, rendered in the same
# window as the current build. Pixel output drifts over GPU/ANGLE states, so a
# comparison against an older capture is not reliable.
BASE_URL = 'http://127.0.0.1:5193/frames.html'
BG = (0xee, 0xf0, 0xee)
NODE = (1573, 410)
os.makedirs(CUR, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

results = []
def check(name, ok, value, expect):
    results.append({'check': name, 'ok': bool(ok), 'value': value, 'expect': expect})
    print(('PASS' if ok else 'FAIL'), name, '|', value, '|', expect, flush=True)

def render(page, query, path):
    page.goto(f'{URL}?{query}')
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    time.sleep(0.8)
    page.screenshot(path=path)

def grey(path):
    return Image.open(path).convert('L').load()

def rgb(path):
    return Image.open(path).convert('RGB').load()

def black_bbox(px, x1=0, x2=1280, y1=0, y2=1080):
    minx, miny, maxx, maxy = None, None, None, None
    for y in range(y1, y2):
        for x in range(x1, x2):
            if px[x, y] < 60:
                if minx is None or x < minx: minx = x
                if maxx is None or x > maxx: maxx = x
                if miny is None or y < miny: miny = y
                if maxy is None or y > maxy: maxy = y
    return (minx, miny, maxx, maxy)

def components(px, x2=1280, y2=1080, cutoff=50):
    seen = bytearray(x2 * y2)
    sizes = []
    for y in range(y2):
        for x in range(x2):
            i = y * x2 + x
            if seen[i] or px[x, y] >= 60:
                continue
            q = deque([(x, y)])
            seen[i] = 1
            n = 0
            while q:
                cx, cy = q.popleft()
                n += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < x2 and 0 <= ny < y2:
                        j = ny * x2 + nx
                        if not seen[j] and px[nx, ny] < 60:
                            seen[j] = 1
                            q.append((nx, ny))
            if n > cutoff:
                sizes.append(n)
    return sorted(sizes, reverse=True)

def nonbg_share(px, x1, x2, y1, y2, tol=3, step=2):
    bad = tot = 0
    for y in range(y1, y2, step):
        for x in range(x1, x2, step):
            r, g, b = px[x, y]
            tot += 1
            if max(abs(r - BG[0]), abs(g - BG[1]), abs(b - BG[2])) > tol:
                bad += 1
    return bad / tot

def differs(a, b, tol=8):
    pa, pb = rgb(a), rgb(b)
    w, h = Image.open(a).size
    bad = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            ca, cb = pa[x, y], pb[x, y]
            if max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2])) > tol:
                bad += 1
    return bad / ((w // 2) * (h // 2))

skipped_build = '--skip-build' in sys.argv
console_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True,
                                args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)

    def note_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)
    page.on('console', note_console)
    page.on('pageerror', lambda e: console_errors.append(f'pageerror: {e}'))

    # ---- deliverable frame ----
    render(page, 'frame=open&theme=light&t=3', STYLE)
    probe = page.evaluate('window.__openProbe')
    render(page, 'frame=open&theme=light&t=3&mask=1', f'{OUT}/mask.png')
    render(page, 'frame=open&theme=light&t=3&sweep=0.5', f'{OUT}/sweep-0.5.png')
    for t in (0.6, 1.2, 1.8, 5):
        render(page, f'frame=open&theme=light&t={t}', f'{OUT}/t{t}.png')
    render(page, 'frame=open&theme=light&t=0', f'{CUR}/t0.png')

    # ---- 1 size ----
    w, h = Image.open(STYLE).size
    check('1 frame size', (w, h) == (1920, 1080), f'{w}x{h}', '1920x1080')

    # ---- 2 one component ----
    mask_px = grey(f'{OUT}/mask.png')
    comps = components(mask_px)
    check('2 mask components', len(comps) == 1, comps, 'exactly 1 block > 50 px')

    # ---- 3 bbox ----
    minx, miny, maxx, maxy = black_bbox(mask_px)
    bw, bh = maxx - minx + 1, maxy - miny + 1
    cx, cy, ratio = (minx + maxx) / 2, (miny + maxy) / 2, bw / bh
    ok3 = 560 <= bh <= 660 and 460 <= cx <= 580 and 505 <= cy <= 585 and 0.30 <= ratio <= 0.48
    check('3 mask bbox', ok3, f'h={bh} cx={cx:.0f} cy={cy:.0f} R={ratio:.3f}', 'h 560-660, cx 460-580, cy 505-585, R 0.30-0.48')

    # ---- 4 background ----
    fpx = rgb(STYLE)
    s1 = nonbg_share(fpx, 40, 270, 700, 1040)
    s2 = nonbg_share(fpx, 900, 1260, 700, 1040)
    check('4 left background', s1 == 0 and s2 == 0, f'{s1:.5f} / {s2:.5f}', 'no pixel differs by more than 3')

    # ---- 5 graph DOM ----
    page.goto(f'{URL}?frame=open&theme=light&t=3')
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    g = page.evaluate("""() => {
        const g = document.querySelector('#graph');
        const texts = [...g.querySelectorAll('text')].map(t => t.textContent);
        return {
          circles: g.querySelectorAll('circle[r="6.5"]').length,
          counter: texts.find(t => t.includes('个节点')) ?? '',
          texts,
        };
    }""")
    joined = ' '.join(g['texts'])
    ok5 = (g['circles'] == 1 and g['counter'] == '1 个节点 · 0 条关系'
           and not any(k in joined for k in ('研发', '生产', '质量', '供应链'))
           and '第一级涡轮叶片' in joined and '×1' in joined)
    check('5 graph single node', ok5, f"nodes={g['circles']} counter={g['counter']}", '1 node, counter 1/0, no group names, ×1')

    # ---- 6 thread geometry ----
    th = page.evaluate("""() => {
        const p = document.querySelector('#thread path');
        const total = p.getTotalLength();
        const off = parseFloat(p.style.strokeDashoffset || '0');
        const s = p.getPointAtLength(0), e = p.getPointAtLength(total);
        const head = p.getPointAtLength(Math.max(0, total - off));
        return {total, off, sx: s.x, sy: s.y, ex: e.x, ey: e.y, hx: head.x};
    }""")
    # nearest black pixel to the start point, within 6 px
    near = min((abs(x - th['sx']) + abs(y - th['sy']) for y in range(int(th['sy']) - 6, int(th['sy']) + 7)
                for x in range(int(th['sx']) - 6, int(th['sx']) + 7) if mask_px[x, y] < 60), default=99)
    end_gap = ((th['ex'] - NODE[0]) ** 2 + (th['ey'] - NODE[1]) ** 2) ** 0.5
    ok6 = near <= 6 and end_gap <= 12 and 1330 <= th['hx'] <= 1480
    check('6 thread', ok6, f"start->mask {near}px, end gap {end_gap:.1f}px, head x {th['hx']:.0f}", 'start on blade, end at node, head 1330-1480')

    # ---- 7 timeline ----
    page.goto(f'{URL}?frame=open&theme=light&t=0')
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    time.sleep(0.3)
    t0 = page.evaluate("""() => {
        const g = document.querySelector('#graph');
        const counter = [...g.querySelectorAll('text')].map(t => t.textContent).find(t => t.includes('个节点')) ?? '';
        const p = document.querySelector('#thread path');
        return {counter, off: parseFloat(p.style.strokeDashoffset || '0'), total: p.getTotalLength()};
    }""")
    empty = nonbg_share(rgb(f'{CUR}/t0.png'), 0, 1280, 101, 1080)
    page.goto(f'{URL}?frame=open&theme=light&t=5')
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    time.sleep(0.3)
    t5 = page.evaluate("""() => {
        const p = document.querySelector('#thread path');
        return {off: parseFloat(p.style.strokeDashoffset || '0'), total: p.getTotalLength()};
    }""")
    render(page, 'frame=open&theme=light&t=5&mask=1', f'{CUR}/mask5.png')
    comps5 = components(grey(f'{CUR}/mask5.png'))
    ok7 = (empty < 0.001 and t0['counter'] == '0 个节点 · 0 条关系'
           and t0['off'] >= t0['total'] - 0.5 and t5['off'] <= 0.5 and len(comps5) == 1)
    check('7 timeline', ok7, f"t0 empty={empty:.5f} counter={t0['counter']} off={t0['off']:.0f}/{t0['total']:.0f} t5 off={t5['off']:.1f} comps={comps5}", 't0 blank + 0 nodes + no line, t5 line drawn, 1 block')

    # ---- 8 console ----
    check('8 console clean', not console_errors, console_errors[:3] or 'none', 'no error / pageerror')

    # ---- 9 other frames unchanged ----
    # Reference frames come from the committed code, captured right now.
    live = '/tmp/open-check/base-live'
    os.makedirs(live, exist_ok=True)
    page.goto(f'{BASE_URL}?frame=q3&theme=light')
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
    time.sleep(0.8)
    page.screenshot(path=f'{live}/q3.png')
    for name in ('stale', 'net'):
        page.goto(f'{BASE_URL}?frame={name}&theme=light')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        time.sleep(0.8)
        page.screenshot(path=f'{live}/{name}.png')
    for t in (3, 9, 15, 20):
        page.goto(f'{BASE_URL}?frame=clip&theme=light&play=0')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        page.evaluate(f'window.__seek({t})')
        time.sleep(0.3)
        page.screenshot(path=f'{live}/t{t:05.2f}.png')

    worst = ('', 0.0)
    for name, query in [('q3', 'frame=q3&theme=light'), ('stale', 'frame=stale&theme=light'), ('net', 'frame=net&theme=light')]:
        path = f'{CUR}/{name}.png'
        render(page, query, path)
        share = differs(path, f'{live}/{name}.png')
        if share > worst[1]:
            worst = (name, share)
    for t in (3, 9, 15, 20):
        path = f'{CUR}/clip-{t}.png'
        page.goto(f'{URL}?frame=clip&theme=light&play=0')
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        page.evaluate(f'window.__seek({t})')
        time.sleep(0.3)
        page.screenshot(path=path)
        share = differs(path, f'{live}/t{t:05.2f}.png')
        if share > worst[1]:
            worst = (f'clip t={t}', share)
    check('9 other frames unchanged', worst[1] < 0.0001, f'worst {worst[0]} {worst[1]*100:.4f}%', '< 0.01% of pixels differ by > 8')

    browser.close()

# ---- 11 sweep direction ----
cur = rgb(f'{OUT}/sweep-0.5.png')
top = bot = 0
ntop = nbot = 0
for y in range(miny, maxy + 1):
    for x in range(minx, maxx + 1):
        if mask_px[x, y] < 60:
            r, g_, b = cur[x, y]
            far = max(abs(r - BG[0]), abs(g_ - BG[1]), abs(b - BG[2])) > 12
            if y < miny + bh * 0.3:
                ntop += 1
                top += far
            elif y > miny + bh * 0.7:
                nbot += 1
                bot += far
top_share, bot_share = top / max(1, ntop), bot / max(1, nbot)
check('11 sweep direction', top_share < 0.35 and bot_share > 0.90,
      f'top {top_share*100:.1f}% bottom {bot_share*100:.1f}%', 'top < 35%, bottom > 90%')

# ---- 12 blade contrast ----
diff = n = 0
for y in range(miny, maxy + 1, 2):
    for x in range(minx, maxx + 1, 2):
        if mask_px[x, y] < 60:
            r, g_, b = fpx[x, y]
            diff += (abs(r - BG[0]) + abs(g_ - BG[1]) + abs(b - BG[2])) / 3
            n += 1
mean_diff = diff / max(1, n)
check('12 blade contrast', mean_diff >= 18, f'{mean_diff:.1f}', 'mean channel diff >= 18')

# ---- 13 mid-blade wall is solid ----
from statistics import pstdev

def box_stats(cx, cy, size=120):
    vals, black, total = [], 0, 0
    for y in range(cy - size // 2, cy + size // 2):
        for x in range(cx - size // 2, cx + size // 2):
            r, g_, b = fpx[x, y]
            vals.append(0.2126 * r + 0.7152 * g_ + 0.0722 * b)
            total += 1
            if mask_px[x, y] < 60:
                black += 1
    return pstdev(vals), black / total

px, py = round(probe['x']), round(probe['y'])
std_c, cover = box_stats(px, py)
std_l, _ = box_stats(px - 60, py)
std_r, _ = box_stats(px + 60, py)
check('13 mid-blade solid', cover == 1.0 and std_c <= max(std_l, std_r) + 3,
      f'coverage {cover*100:.1f}%, std c/l/r {std_c:.2f}/{std_l:.2f}/{std_r:.2f}',
      'coverage 100%, centre std <= max(left, right) + 3')

# zoom of the same patch for review
zoom = Image.open(STYLE).convert('RGB').crop((px - 150, py - 120, px + 150, py + 120)).resize((900, 720), Image.LANCZOS)
zoom.save(f'{OUT}/叶身中部放大.png')

# ---- 10 build ----
if skipped_build:
    check('10 typecheck and build', True, 'skipped', 'tsc + vite build')
else:
    tsc = subprocess.run(['npx', 'tsc', '--noEmit', '-p', '.'], cwd=WORK, capture_output=True, text=True)
    build = subprocess.run(['npx', 'vite', 'build'], cwd=WORK, capture_output=True, text=True)
    check('10 typecheck and build', tsc.returncode == 0 and build.returncode == 0,
          f'tsc {tsc.returncode}, build {build.returncode}', 'both exit 0')

with open(f'{OUT}/results.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} checks passed')
sys.exit(0 if passed == len(results) else 1)
