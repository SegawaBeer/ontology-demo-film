"""Fourteen automated checks for opening milestone one (0:00-0:09.6)."""
import json, math, os, subprocess, sys, time
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
WORK = f'{ROOT}/.claude/worktrees/style-frames'
OUT = f'{ROOT}/review/opening'
STYLE = f'{ROOT}/样式图/开头0-03一枚叶片-浅色.png'
URL = 'http://127.0.0.1:5192/frames.html'
BASE_URL = 'http://127.0.0.1:5193/frames.html'
BG = (0xee, 0xf0, 0xee)
TMP = '/tmp/opening-check'
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

results = []
def check(name, ok, value, expect):
    results.append({'check': name, 'ok': bool(ok), 'value': value, 'expect': expect})
    print(('PASS' if ok else 'FAIL'), name, '|', value, '|', expect, flush=True)

def rgb(path):
    im = Image.open(path).convert('RGB')
    return im, im.load()

def share_diff(a, b, tol=8):
    ia, pa = rgb(a); ib, pb = rgb(b)
    w, h = ia.size
    bad = 0
    for y in range(0, h):
        for x in range(0, w):
            ca, cb = pa[x, y], pb[x, y]
            if max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2])) > tol:
                bad += 1
    return bad / (w * h)

def mask_bbox(path):
    im = Image.open(path).convert('L'); p = im.load()
    minx, miny, maxx, maxy = 1280, 1080, 0, 0
    for y in range(1080):
        for x in range(1280):
            if p[x, y] < 60:
                minx = min(minx, x); maxx = max(maxx, x); miny = min(miny, y); maxy = max(maxy, y)
    return minx, miny, maxx, maxy, p

def near_black(pm, pt, radius=40):
    x0 = max(0, int(pt[0]) - radius); x1 = min(1280, int(pt[0]) + radius)
    y0 = max(0, int(pt[1]) - radius); y1 = min(1080, int(pt[1]) + radius)
    best = 99
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pm[x, y] < 60:
                d = math.dist(pt, (x, y))
                if d < best: best = d
    return best

def nonbg(path, x0, x1, y0, y1):
    _, p = rgb(path)
    bad = total = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = p[x, y]
            total += 1
            if max(abs(r - BG[0]), abs(g - BG[1]), abs(b - BG[2])) > 3:
                bad += 1
    return bad / total

console = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    page.on('console', lambda m: console.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: console.append(f'pageerror: {e}'))

    def go(query, base=False, mask=False):
        url = (BASE_URL if base else URL) + '?' + query
        page.goto(url)
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=120000)
        time.sleep(0.5)

    def shot(query, name, base=False):
        go(query, base)
        path = f'{TMP}/{name}.png'
        page.screenshot(path=path)
        return path

    def probe():
        return page.evaluate('window.__openingProbe()')

    times = ['0.6', '1.2', '1.8', '3', '4.7']
    for t in times:
        shot(f'frame=opening&theme=light&t={t}', f'op-{t}')
        shot(f'frame=open&theme=light&t={t}', f'base-{t}')

    # ---- 2 opening matches the style frame ----
    worst = ('', 0.0)
    for t in times:
        s = share_diff(f'{TMP}/op-{t}.png', f'{TMP}/base-{t}.png')
        if s > worst[1]: worst = (f'open t={t}', s)
    s_style = share_diff(f'{TMP}/op-3.png', STYLE)
    ok2 = worst[1] < 0.0001 and s_style < 0.0001
    check('2 opening matches open', ok2, f'worst {worst[0]} {worst[1]*100:.4f}%, style {s_style*100:.4f}%', '< 0.01%')

    # ---- 3 other frames unchanged ----
    worst = ('', 0.0)
    for name, q in [('q3', 'frame=q3&theme=light'), ('stale', 'frame=stale&theme=light'),
                    ('net', 'frame=net&theme=light'), ('open3', 'frame=open&theme=light&t=3')]:
        cur = f'{TMP}/cur-{name}.png'; ref = f'{TMP}/ref-{name}.png'
        shot(q, f'cur-{name}'); shot(q, f'ref-{name}', base=True)
        s = share_diff(cur, ref)
        if s > worst[1]: worst = (name, s)
    for t in ('3', '9', '15', '20'):
        cur = f'{TMP}/cur-clip{t}.png'; ref = f'{TMP}/ref-clip{t}.png'
        for path, base in ((cur, False), (ref, True)):
            go('frame=clip&theme=light&play=0', base)
            page.evaluate(f'window.__seek({t})')
            time.sleep(0.3)
            page.screenshot(path=path)
        s = share_diff(cur, ref)
        if s > worst[1]: worst = (f'clip {t}', s)
    check('3 other frames unchanged', worst[1] < 0.0001, f'worst {worst[0]} {worst[1]*100:.4f}%', '< 0.01%')

    # ---- 4 pure function of t ----
    def same_probe(a, b):
        if a['blades']['count'] != b['blades']['count']: return False
        if a['graph']['counter'] != b['graph']['counter'] or a['graph']['sub'] != b['graph']['sub']: return False
        if max(abs(x - y) for x, y in zip(a['camera']['position'], b['camera']['position'])) > 1e-9: return False
        if max(abs(x - y) for x, y in zip(a['hero']['matrix'], b['hero']['matrix'])) > 1e-9: return False
        return True
    pure_ok = True; pure_val = []
    for t, prior in (('8.2', '9.5'), ('6.0', '2.0')):
        go(f'frame=opening&theme=light&t={t}')
        p1 = probe(); page.screenshot(path=f'{TMP}/pure-a.png')
        go(f'frame=opening&theme=light&t={prior}')
        page.evaluate(f'window.__seek({t})')
        p2 = probe(); page.screenshot(path=f'{TMP}/pure-b.png')
        same = share_diff(f'{TMP}/pure-a.png', f'{TMP}/pure-b.png') < 0.0001
        pure_ok = pure_ok and same and same_probe(p1, p2)
        pure_val.append(f't={t}: img {same}, probe {same_probe(p1, p2)}')
    check('4 pure function of t', pure_ok, '; '.join(pure_val), 'same image and probe')

    # ---- 5 seat accuracy ----
    go('frame=opening&theme=light&t=0')
    seat = probe()['seatMatrix']
    worst_pos = worst_elem = 0.0
    t = 6.40
    while t <= 7.391:
        page.evaluate(f'window.__seek({t})')
        m = probe()['hero']['matrix']
        worst_pos = max(worst_pos, math.dist(m[12:15], seat[12:15]))
        worst_elem = max(worst_elem, max(abs(m[i] - seat[i]) for i in range(12)))
        t += 0.1
    check('5 seat accuracy', worst_pos <= 0.002 and worst_elem <= 0.01,
          f'pos {worst_pos:.5f}, rot/scale {worst_elem:.5f}', 'pos <= 0.002, orient <= 0.5deg')

    # ---- 6 motion continuity ----
    go('frame=opening&theme=light&t=0')
    samples = []
    n = int((6.5 - 4.9) * 60)
    for i in range(n + 1):
        tt = 4.9 + i / 60
        page.evaluate(f'window.__seek({tt})')
        p = probe()
        samples.append((tt, p['hero']['screen']['x'], p['hero']['screen']['y'], p['hero']['matrix']))
    steps = [math.dist((samples[i][1], samples[i][2]), (samples[i + 1][1], samples[i + 1][2])) for i in range(len(samples) - 1)]
    max_step = max(steps)
    max_jerk = max(abs(steps[i + 1] - steps[i]) for i in range(len(steps) - 1))
    def angle_between(m0, m1):
        def rot(m):
            cols = [[m[0], m[1], m[2]], [m[4], m[5], m[6]], [m[8], m[9], m[10]]]
            out = []
            for c in cols:
                n = math.sqrt(sum(v * v for v in c)) or 1
                out.append([v / n for v in c])
            return [[out[j][i] for j in range(3)] for i in range(3)]
        a, b = rot(m0), rot(m1)
        # relative rotation b * a^T
        rel = [[sum(b[i][k] * a[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
        tr = rel[0][0] + rel[1][1] + rel[2][2]
        return math.degrees(math.acos(max(-1, min(1, (tr - 1) / 2))))
    idx5 = min(range(len(samples)), key=lambda i: abs(samples[i][0] - 5.0))
    w_before = angle_between(samples[idx5 - 1][3], samples[idx5][3]) * 60
    w_after = angle_between(samples[idx5][3], samples[idx5 + 1][3]) * 60
    go('frame=opening&theme=light&t=5.8')
    seat_px = probe()['seat']
    in_left = 0 <= seat_px['x'] <= 1280 and 0 <= seat_px['y'] <= 1080
    go('frame=opening&theme=light&t=6.4')
    box = probe()['hero']['box']
    margin = min(box[0], box[1], 1280 - box[2], 1080 - box[3])
    height = box[3] - box[1]
    ok6 = (max_step <= 40 and max_jerk <= 4 and abs(w_before - w_after) <= 1 and in_left
           and margin >= 40 and 120 <= height <= 420)
    check('6 motion continuity', ok6,
          f'step {max_step:.1f}px jerk {max_jerk:.2f}px w {w_before:.2f}/{w_after:.2f}deg/s seat_in {in_left} margin {margin:.0f} h {height:.0f}',
          'step<=40 jerk<=4 dw<=1 seat inside, 6.4 box in column h 120-420')

    # ---- 7 swap is invisible ----
    a = shot('frame=opening&theme=light&t=7.39', 'swap-a')
    b = shot('frame=opening&theme=light&t=7.40', 'swap-b')
    _, pa = rgb(a); _, pb = rgb(b)
    bad = 0
    for y in range(1080):
        for x in range(1280):
            ca, cb = pa[x, y], pb[x, y]
            if max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2])) > 12: bad += 1
    s7 = bad / (1280 * 1080)
    check('7 swap invisible', s7 < 0.003, f'{s7*100:.3f}%', '< 0.3%')

    # ---- 8 ring view ----
    ring = shot('frame=opening&theme=light&t=7.3&mask=1', 'ring-mask')
    minx, miny, maxx, maxy, _ = mask_bbox(ring)
    h8 = maxy - miny + 1; cx = (minx + maxx) / 2; cy = (miny + maxy) / 2
    edge = min(minx, miny, 1280 - maxx, 1080 - maxy)
    ok8 = 420 <= h8 <= 560 and 560 <= cx <= 720 and 480 <= cy <= 600 and edge >= 40
    check('8 ring view', ok8, f'h {h8} cx {cx:.0f} cy {cy:.0f} edge {edge}', 'h 420-560, cx 560-720, cy 480-600, edge >= 40')

    # ---- 9 ring fills up ----
    def expected(t):
        n = 1
        for k in range(2, 101):
            if t >= 7.45 + 1.15 * math.sqrt((k - 2) / 98): n = k
            else: break
        return n
    go('frame=opening&theme=light&t=0')
    mono = True; match = True; prev = 0
    for i in range(int((8.7 - 7.4) * 60) + 1):
        tt = 7.4 + i / 60
        page.evaluate(f'window.__seek({tt})')
        p = probe()
        count = p['blades']['count']
        if count < prev: mono = False
        if count != expected(tt): match = False
        if p['graph']['sub'] != f'×{max(1, count)}': match = False
        prev = count
    page.evaluate('window.__seek(8.6)')
    final_sub = probe()['graph']['sub']
    ok9 = mono and match and final_sub == '×100'
    check('9 ring fills up', ok9, f'monotonic {mono}, matches formula {match}, 8.6 sub {final_sub}', 'monotonic, matches 4.4, ×100 at 8.6')

    # ---- 10 graph end state ----
    go('frame=opening&theme=light&t=9.6')
    g = probe()['graph']
    texts = ' '.join(g['texts'])
    ok10 = (g['nodes'] == 2 and g['counter'] == '2 个节点 · 1 条关系' and '×100' in texts
            and '涡轮叶环' in texts and not any(k in texts for k in ('研发', '生产', '质量', '供应链', '压气机叶环')))
    check('10 graph end state', ok10, f"nodes {g['nodes']} counter {g['counter']}", '2 nodes, counter 2/1, ×100, no groups')

    # ---- 11 threads ----
    go('frame=opening&theme=light&t=6.0')
    th = probe()['threads'][0]
    pm6 = mask_bbox(shot('frame=opening&theme=light&t=6.0&mask=1', 'thread-6'))[4]
    near1 = near_black(pm6, th['start'])
    go('frame=opening&theme=light&t=7.2')
    th2 = probe()['threads'][0]
    gone = th2['opacity'] <= 0.001 or th2['off'] >= th2['total'] - 0.5
    go('frame=opening&theme=light&t=9.6')
    th3 = probe()['threads'][1]
    pm96 = mask_bbox(shot('frame=opening&theme=light&t=9.6&mask=1', 'thread-96'))[4]
    near2 = near_black(pm96, th3['start'])
    end_gap = math.dist(th3['end'], (1573, 330))
    ok11 = near1 <= 6 and gone and near2 <= 6 and end_gap <= 9
    check('11 threads', ok11, f'start1 {near1:.1f}px, t7.2 gone {gone}, start2 {near2:.1f}px, end {end_gap:.1f}px',
          'start<=6, first gone at 7.2, start2<=6, end<=9')

    # ---- 12 flash ----
    vals = []
    for t in ('8.75', '9.05', '9.35'):
        p = shot(f'frame=opening&theme=light&t={t}', f'flash-{t}')
        pm = mask_bbox(shot(f'frame=opening&theme=light&t={t}&mask=1', f'flash-{t}-mask'))[4]
        _, pc = rgb(p)
        total = 0; cnt = 0
        for y in range(1080):
            for x in range(1280):
                if pm[x, y] < 60:
                    r, g, b = pc[x, y]
                    total += b - r; cnt += 1
        vals.append(total / max(1, cnt))
    ok12 = (vals[1] - vals[0] >= 15) and abs(vals[2] - vals[0]) <= 4
    check('12 flash', ok12, ' / '.join(f'{v:.1f}' for v in vals), '9.05 - 8.75 >= 15, 9.35 ~ 8.75')

    # ---- 13 background ----
    worst13 = 0.0
    for t in ('0', '3', '9.6'):
        p = shot(f'frame=opening&theme=light&t={t}', f'bg-{t}')
        worst13 = max(worst13, nonbg(p, 40, 200, 900, 1040), nonbg(p, 1100, 1260, 900, 1040))
    check('13 background clean', worst13 == 0.0, f'{worst13:.5f}', 'all pixels within 3 of #eef0ee')

    # ---- 14 console ----
    check('14 console clean', not console, console[:3] or 'none', 'no error / pageerror')
    browser.close()

# ---- 1 build ----
tsc = subprocess.run(['npx', 'tsc', '--noEmit', '-p', '.'], cwd=WORK, capture_output=True, text=True)
build = subprocess.run(['npx', 'vite', 'build'], cwd=WORK, capture_output=True, text=True)
check('1 typecheck and build', tsc.returncode == 0 and build.returncode == 0,
      f'tsc {tsc.returncode}, build {build.returncode}', 'both exit 0')

with open(f'{OUT}/results.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} checks passed')
sys.exit(0 if passed == len(results) else 1)
