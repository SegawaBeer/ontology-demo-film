"""Checks 29-38 for opening milestone three A."""
import json, math, os, sys, time
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
OUT = f'{ROOT}/review/opening/m3'
URL = 'http://127.0.0.1:5192/frames.html'
BASE_URL = 'http://127.0.0.1:5193/frames.html'
BG = (238, 240, 238)
TMP = '/tmp/opening-check3'
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

results = []
def check(name, ok, value, expect):
    results.append({'check': name, 'ok': bool(ok), 'value': value, 'expect': expect})
    print(('PASS' if ok else 'FAIL'), name, '|', value, '|', expect, flush=True)

def pixels(path):
    return Image.open(path).convert('RGB').load()

def far(px, x, y, tol=40):
    r, g, b = px[x, y]
    return max(abs(r - BG[0]), abs(g - BG[1]), abs(b - BG[2])) > tol

def share(a, b, region, tol=8):
    pa, pb = pixels(a), pixels(b)
    x0, y0, x1, y1 = region
    bad = total = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            ca, cb = pa[x, y], pb[x, y]
            total += 1
            if max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2])) > tol:
                bad += 1
    return bad / max(1, total)

PIECES = [
    ('combustor', ['combustor.cans', 'combustor.casing', 'combustor.injectors', 'combustor.inner-shell'], 17.00, 0.20, 0.60),
    ('core', ['core-casing.bolts', 'core-casing.drum', 'core-casing.inner-wall', 'core-casing.tiles', 'turbine.band', 'turbine.inner-cone'], 17.80, 0.20, 0.70),
    ('fanhub', ['fan.hub', 'fan.inner-shroud'], 18.70, 0.15, 0.55),
    ('cowl', ['fan-cowl.aft', 'fan-cowl.lip', 'fan-cowl.shell'], 20.20, 0.20, 0.90),
    ('nacelle', ['nacelle.duct'], 20.20, 0.20, 0.90),
    ('exhaust', ['exhaust.bolts', 'exhaust.fittings', 'exhaust.nozzle', 'exhaust.tail-cone'], 21.30, 0.15, 0.60),
    ('spinner', ['fan.spinner'], 21.30, 0.15, 0.60),
]

console = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True,
                                 args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    page.on('console', lambda m: console.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: console.append(f'pageerror: {e}'))
    extra = [browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1) for _ in range(2)]

    def go(query, base=False, which=None):
        pg = which or page
        pg.goto((BASE_URL if base else URL) + '?' + query)
        pg.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.3)
        return pg

    def probe():
        return page.evaluate('window.__openingProbe()')

    # ---- 29 join with a15ba3a ----
    worst = ('', 0.0); cam_ok = True
    for tt in ('3.0', '8.0', '12.0', '15.0', '17.0'):
        go(f'frame=opening&theme=light&t={tt}')
        page.screenshot(path=f'{TMP}/j-now.png')
        cam_now = probe()['camera']
        go(f'frame=opening&theme=light&t={tt}', base=True)
        page.screenshot(path=f'{TMP}/j-base.png')
        cam_base = probe()['camera']
        s = max(share(f'{TMP}/j-now.png', f'{TMP}/j-base.png', (0, 0, 1280, 1080)),
                share(f'{TMP}/j-now.png', f'{TMP}/j-base.png', (1280, 0, 1920, 1080)))
        if s > worst[1]: worst = (tt, s)
        cam_ok = cam_ok and max(abs(x - y) for x, y in zip(cam_now['position'], cam_base['position'])) < 1e-6
    check('29 join', worst[1] < 0.0001 and cam_ok, f'worst {worst[0]}s {worst[1]*100:.4f}%, camera {cam_ok}', '< 0.01% and identical camera')

    # ---- 30 parts arrive ----
    schedule = {}
    for name, ids, start, o0, sweep in PIECES:
        for cid in ids:
            schedule[cid] = start
    go('frame=opening&theme=light&t=17.0')
    firsts = {}
    for i in range(int((22.9 - 17.0) * 10) + 1):
        tt = 17.0 + i * 0.1
        page.evaluate(f'window.__seek({tt})')
        comps = probe()['components']
        for cid in schedule:
            if cid not in firsts and comps.get(cid):
                firsts[cid] = tt
    late = [(c, firsts.get(c), s) for c, s in schedule.items() if firsts.get(c) is None or abs(firsts[c] - s) > 0.1 + 1e-6]
    go('frame=opening&theme=light&t=22.0')
    parts = probe()['visibleParts']
    check('30 parts arrive', not late and parts == 2027, f'{len(late)} mismatches, parts {parts}', 'schedule within a frame, 2027 parts')

    # ---- 31 outline first for every piece and three fan blades ----
    bad31 = []; rows31 = []
    for name, ids, start, o0, sweep in PIECES:
        solo = ",".join(ids)
        tt = start + o0 * 0.6
        mp = go(f'frame=opening&theme=light&mask=part:{solo}&t={tt:.3f}', which=extra[0])
        mp.screenshot(path=f'{TMP}/m31.png')
        on = go(f'frame=opening&theme=light&solo={solo}&t={tt:.3f}', which=page)
        on.screenshot(path=f'{TMP}/o31.png')
        off = go(f'frame=opening&theme=light&solo={solo}&nolines=1&noflash=1&t={tt:.3f}', which=extra[1])
        off.screenshot(path=f'{TMP}/f31.png')
        pm = pixels(f'{TMP}/m31.png'); pa = pixels(f'{TMP}/o31.png'); pb = pixels(f'{TMP}/f31.png')
        pts = [(x, y) for y in range(100, 1080, 2) for x in range(0, 1280, 2) if max(pm[x, y]) < 245]
        if not pts:
            bad31.append(f'{name} empty'); continue
        o = sum(1 for (x, y) in pts if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20) / len(pts)
        g = sum(1 for (x, y) in pts if far(pb, x, y)) / len(pts)
        rows31.append([name, round(o, 3), round(g, 3)])
        if o < 0.01 or g >= 0.05:
            bad31.append(f'{name} O={o*100:.1f}% G={g*100:.1f}%')
    with open(f'{OUT}/m3-outline.json', 'w') as f:
        json.dump(rows31, f)
    check('31 outline first', not bad31, '; '.join(bad31[:2]) if bad31 else str(rows31), 'outline instant O >= 1%, G < 5%')

    # ---- 32 instanced parts do show outlines ----
    bad32 = []
    for part in ('combustor.injectors', 'core-casing.tiles', 'core-casing.bolts', 'fan.hub', 'exhaust.bolts'):
        tt = {'combustor.injectors': 17.1, 'core-casing.tiles': 17.9, 'core-casing.bolts': 17.9,
              'fan.hub': 18.8, 'exhaust.bolts': 21.4}[part]
        mp = go(f'frame=opening&theme=light&mask=part:{part}&t={tt:.2f}', which=extra[0])
        mp.screenshot(path=f'{TMP}/m32.png')
        on = go(f'frame=opening&theme=light&t={tt:.2f}', which=page); on.screenshot(path=f'{TMP}/o32.png')
        off = go(f'frame=opening&theme=light&nolines=1&t={tt:.2f}', which=extra[1]); off.screenshot(path=f'{TMP}/f32.png')
        pm = pixels(f'{TMP}/m32.png'); pa = pixels(f'{TMP}/o32.png'); pb = pixels(f'{TMP}/f32.png')
        pts = [(x, y) for y in range(100, 1080, 2) for x in range(0, 1280, 2) if max(pm[x, y]) < 245]
        if not pts:
            bad32.append(f'{part} empty'); continue
        o = sum(1 for (x, y) in pts if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20) / len(pts)
        if o < 0.01:
            bad32.append(f'{part} O={o*100:.1f}%')
    check('32 instanced outlines', not bad32, '; '.join(bad32) if bad32 else 'all five above 1%', 'O >= 1% at the outline instant')

    # ---- 33 both sides close ----
    spans = {'cowl': [], 'nacelle': []}
    go('frame=opening&theme=light&t=20.2')
    for i in range(10):
        tt = 20.2 + i * 0.1
        for name, ids in (('cowl', PIECES[3][1]), ('nacelle', PIECES[4][1])):
            solo = ",".join(ids)
            mp = go(f'frame=opening&theme=light&mask=part:{solo}&t={tt:.2f}', which=extra[0])
            mp.screenshot(path=f'{TMP}/c-mask.png')
            on = go(f'frame=opening&theme=light&solo={solo}&t={tt:.2f}', which=page)
            on.screenshot(path=f'{TMP}/c-on.png')
            pm = pixels(f'{TMP}/c-mask.png'); pa = pixels(f'{TMP}/c-on.png')
            xs = [x for y in range(100, 1080, 4) for x in range(0, 1280, 4)
                  if max(pm[x, y]) < 245 and far(pa, x, y)]
            spans[name].append((min(xs), max(xs)) if xs else (0, 0))
    ok33 = True
    for name in ('cowl', 'nacelle'):
        lo = [s[0] for s in spans[name]]; hi = [s[1] for s in spans[name]]
        grow = all(lo[i + 1] >= lo[i] - 2 for i in range(len(lo) - 1)) if name == 'cowl' else all(hi[i + 1] <= hi[i] + 2 for i in range(len(hi) - 1))
        full = (hi[-1] - lo[-1]) > 0.9 * (max(s[1] for s in spans[name]) - min(s[0] for s in spans[name]))
        ok33 = ok33 and grow and full
    check('33 both sides close', ok33, f'cowl {spans["cowl"][0]}->{spans["cowl"][-1]}, nacelle {spans["nacelle"][0]}->{spans["nacelle"][-1]}',
          'each side grows monotonically towards its end')

    # ---- 34 stays in frame ----
    worst34 = (999, 0)
    go('frame=opening&theme=light&mask=1&t=17.0')
    for i in range(int((23.0 - 17.0) * 10) + 1):
        tt = 17.0 + i * 0.1
        page.evaluate(f'window.__seek({tt})')
        page.screenshot(path=f'{TMP}/f34.png')
        px = Image.open(f'{TMP}/f34.png').convert('L').load()
        minx, miny, maxx, maxy = 1280, 1080, 0, 0
        for y in range(1080):
            for x in range(1280):
                if px[x, y] < 60:
                    if x < minx: minx = x
                    if x > maxx: maxx = x
                    if y < miny: miny = y
                    if y > maxy: maxy = y
        edge = min(minx, miny, 1280 - maxx, 1080 - maxy)
        if edge < worst34[0]:
            worst34 = (edge, round(tt, 1))
    check('34 stays in frame', worst34[0] >= 24, f'worst {worst34[0]}px at {worst34[1]}s', '>= 24px from every edge')

    # ---- 35 camera ----
    go('frame=opening&theme=light&t=21.9')
    p1 = probe(); fit = p1['fit']
    still = True
    for tt in (22.0, 22.5, 23.0):
        page.evaluate(f'window.__seek({tt})')
        pr = probe()
        still = still and max(abs(a - b) for a, b in zip(pr['camera']['position'], p1['camera']['position'])) < 1e-6
    dist = max(max(abs(a - b) for a, b in zip(p1['camera']['position'], fit['position'])),
               max(abs(a - b) for a, b in zip(p1['camera']['target'], fit['target'])))
    go('frame=opening&theme=light&t=17.0')
    pos = []
    for i in range(int((21.9 - 17.0) * 60) + 1):
        page.evaluate(f'window.__seek({17.0 + i / 60})')
        pos.append(probe()['camera']['position'])
    steps = [math.dist(pos[i], pos[i + 1]) for i in range(len(pos) - 1)]
    jerks = [abs(steps[i + 1] - steps[i]) for i in range(len(steps) - 1)]
    med = sorted(steps)[len(steps) // 2]; medj = sorted(jerks)[len(jerks) // 2]
    ok35 = still and dist <= 0.002 and max(steps) <= 4 * max(med, 1e-9) and max(jerks) <= 4 * max(medj, 1e-9)
    check('35 camera', ok35, f'still {still}, fit gap {dist:.4f}, step {max(steps):.4f}/{med:.4f}, jerk {max(jerks):.4f}/{medj:.4f}',
          'still after 21.9, fit gap <= 0.002, smooth')

    # ---- 36 graph ----
    go('frame=opening&theme=light&t=22.35')
    pr = probe(); g = pr['graph']
    texts = ' '.join(g['texts'])
    edges = page.evaluate("() => [...document.querySelectorAll('#graph path')].filter(p => p.getAttribute('stroke') === 'var(--lit)').length")
    ok36 = (g['nodes'] == 21 and g['counter'] == '21 个节点 · 20 条关系' and edges == 20
            and '转子' not in texts and '3 号发动机' not in texts)
    node_times = {'m-comb': 17.0, 'm-core': 17.8, 'm-fan': 18.7, 'c-fan': 19.1, 'm-nac': 20.2,
                  'm-cowl': 20.2, 'm-exh': 21.3, 'e7': 22.0}
    go('frame=opening&theme=light&t=17.0')
    mism = []
    for i in range(int((22.9 - 17.0) * 10) + 1):
        tt = 17.0 + i * 0.1
        page.evaluate(f'window.__seek({tt})')
        ids = set(probe()['graph']['ids'])
        for node, when in node_times.items():
            if (node in ids) != (tt >= when - 1 / 60):
                mism.append((round(tt, 1), node))
    ok36 = ok36 and not mism
    check('36 graph', ok36, f"{g['nodes']} nodes, {g['counter']}, {edges} edges, {len(mism)} timing",
          '21 nodes, 20 edges, no forbidden names, times within a frame')

    # ---- 37 flash ----
    bad37 = []
    for name, ids, start, o0, sweep in PIECES:
        solo = ",".join(ids)
        T = start + sweep
        mp = go(f'frame=opening&theme=light&mask=part:{solo}&t={T + 0.2:.3f}', which=extra[0])
        mp.screenshot(path=f'{TMP}/m37.png')
        pm = pixels(f'{TMP}/m37.png')
        on = go(f'frame=opening&theme=light&solo={solo}&t={T + 0.2:.3f}', which=page); on.screenshot(path=f'{TMP}/o37.png')
        off = go(f'frame=opening&theme=light&solo={solo}&noflash=1&t={T + 0.2:.3f}', which=extra[1]); off.screenshot(path=f'{TMP}/f37.png')
        pa = pixels(f'{TMP}/o37.png'); pb = pixels(f'{TMP}/f37.png')
        pts = [(x, y) for y in range(100, 1080, 2) for x in range(0, 1280, 2)
               if max(pm[x, y]) < 245 and max(abs(pb[x, y][i] - BG[i]) for i in range(3)) > 12]
        if not pts:
            bad37.append(f'{name} empty'); continue
        d = sum((pa[x, y][2] - pa[x, y][0]) - (pb[x, y][2] - pb[x, y][0]) for (x, y) in pts) / len(pts)
        if d < 10:
            bad37.append(f'{name} {d:+.0f}')
    go('frame=opening&theme=light&t=22.2')
    page.screenshot(path=f'{TMP}/e7-on.png')
    go('frame=opening&theme=light&t=22.2&noflash=1', which=extra[1])
    extra[1].screenshot(path=f'{TMP}/e7-off.png')
    pa = pixels(f'{TMP}/e7-on.png'); pb = pixels(f'{TMP}/e7-off.png')
    e7px = sum(1 for y in range(1080) for x in range(1280) if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 8)
    check('37 flash', not bad37 and e7px >= 20000, '; '.join(bad37[:2]) if bad37 else f'e7 {e7px}px',
          'each piece >= +10 blue-red, e7 >= 20,000 px')

    # ---- 38 rotor ----
    go('frame=opening&theme=light&t=22.0')
    r22 = probe()['rotor']
    bad38 = []
    for i in range(int((23.0 - 22.0) * 60) + 1):
        tt = 22.0 + i / 60
        page.evaluate(f'window.__seek({tt})')
        got = probe()['rotor']
        u = min(1, (tt - 22.0) / 1.2)
        want = (360 / 5.4) * (1.2 * (u ** 6 - 3 * u ** 5 + 2.5 * u ** 4) + max(0, tt - 23.2))
        if abs(got - want) > 0.01:
            bad38.append(f'{tt:.2f}s {got:.2f} vs {want:.2f}')
            break
    page.evaluate('window.__seek(22.9)')
    page.evaluate('window.__seek(22.5)')
    a = probe()['rotor']
    page.screenshot(path=f'{TMP}/r-a.png')
    go('frame=opening&theme=light&t=22.5')
    b = probe()['rotor']
    page.screenshot(path=f'{TMP}/r-b.png')
    pure = abs(a - b) < 1e-9 and share(f'{TMP}/r-a.png', f'{TMP}/r-b.png', (0, 0, 1280, 1080)) < 0.0001
    go('frame=opening&theme=light&t=22.5')
    page.screenshot(path=f'{TMP}/rot-on.png')
    go('frame=opening&theme=light&t=22.5&norotor=1', which=extra[1])
    extra[1].screenshot(path=f'{TMP}/rot-off.png')
    pa = pixels(f'{TMP}/rot-on.png'); pb = pixels(f'{TMP}/rot-off.png')
    fan_mask = go('frame=opening&theme=light&mask=part:fan.blades&t=22.5', which=extra[0])
    fan_mask.screenshot(path=f'{TMP}/fan-mask.png')
    pm = pixels(f'{TMP}/fan-mask.png')
    fan_px = sum(1 for y in range(0, 1080, 2) for x in range(0, 1280, 2)
                 if max(pm[x, y]) < 245 and max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20)
    cowl_mask = go('frame=opening&theme=light&mask=part:fan-cowl.aft,fan-cowl.lip,fan-cowl.shell&t=22.5', which=extra[0])
    cowl_mask.screenshot(path=f'{TMP}/cowl-mask.png')
    pm2 = pixels(f'{TMP}/cowl-mask.png')
    cowl_px = sum(1 for y in range(0, 1080, 2) for x in range(0, 1280, 2)
                  if max(pm2[x, y]) < 245 and max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20)
    ok38 = not bad38 and pure and fan_px >= 2000 and cowl_px == 0
    check('38 rotor', ok38, f'{bad38[:1]} pure {pure}, fan {fan_px}, cowl {cowl_px}',
          'rotor matches the formula, pure of t, fan turns, cowl does not')

    check('14c console during milestone three', not console, console[:2] or 'none', 'no error / pageerror')
    browser.close()

with open(f'{OUT}/results.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} milestone-three checks passed')
sys.exit(0 if passed == len(results) else 1)
