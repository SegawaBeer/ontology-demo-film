"""Checks 29-38 for opening milestone three A."""
import json, math, os, sys, time
from PIL import Image, ImageFilter, ImageChops
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

# Keeps the camera each WebGL renderer really renders with, so frame=net can be
# compared against the opening without any probe of its own.
THREE_PROBE = """
window.__THREE_DEVTOOLS__ = new EventTarget();
window.__THREE_DEVTOOLS__.addEventListener('observe', e => {
  const o = e.detail;
  if (o && typeof o.render === 'function' && o.domElement) {
    const orig = o.render.bind(o);
    o.render = (scene, cam) => { window.__lastCam = cam; return orig(scene, cam); };
  }
});"""

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


def column(path):
    """Left column and its distance from the background, as pictures."""
    im = Image.open(path).convert('RGB').crop((0, 0, 1280, 1080))
    d = ImageChops.difference(im, Image.new('RGB', im.size, BG)).convert('L')
    return im, d

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
    # The depth shells were reordered, so from 9.6 s on metal that used to be
    # erased may come back; nothing else may change. 3.0 and 8.0 must still match
    # exactly. 17.00 is the combustor's first frame, so 16.98 is compared and
    # 17.00 only for the camera.
    worst = ('', 0.0); cam_ok = True
    for tt in ('3.0', '8.0'):
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
    excused_rows = []
    for tt in ('12.0', '15.0', '16.98'):
        go(f'frame=opening&theme=light&t={tt}')
        page.screenshot(path=f'{TMP}/j-now.png')
        cam_now = probe()['camera']
        go(f'frame=opening&theme=light&t={tt}', base=True)
        page.screenshot(path=f'{TMP}/j-base.png')
        cam_base = probe()['camera']
        cam_ok = cam_ok and max(abs(x - y) for x, y in zip(cam_now['position'], cam_base['position'])) < 1e-6
        right = share(f'{TMP}/j-now.png', f'{TMP}/j-base.png', (1280, 0, 1920, 1080))
        if right > worst[1]: worst = (tt + ' right', right)
        now, now_d = column(f'{TMP}/j-now.png')
        base, base_d = column(f'{TMP}/j-base.png')
        changed = ImageChops.difference(now, base).convert('L').point(lambda v: 255 if v > 8 else 0)
        # Only metal that a15ba3a had erased may appear: base near background and
        # the new picture clearly not.
        returnable = ImageChops.multiply(base_d.point(lambda v: 255 if v < 15 else 0),
                                         now_d.point(lambda v: 255 if v > 25 else 0))
        rest = ImageChops.subtract(changed, returnable)
        rest_share = rest.histogram()[255] / (1280 * 1080)
        excused_rows.append((tt, changed.histogram()[255], returnable.histogram()[255], round(rest_share * 100, 4)))
        if rest_share > 0.0005: worst = (tt + ' left', rest_share)
    go('frame=opening&theme=light&t=17.0')
    cam_now = probe()['camera']
    go('frame=opening&theme=light&t=17.0', base=True)
    cam_base = probe()['camera']
    cam_ok = cam_ok and max(abs(x - y) for x, y in zip(cam_now['position'], cam_base['position'])) < 1e-6
    joined = (worst[1] < 0.0001 and cam_ok)
    check('29 join', joined,
          f'worst {worst[0]}s {worst[1]*100:.4f}%, camera {cam_ok}, allowed {excused_rows}',
          '3.0/8.0 < 0.01%, later frames only returning metal < 0.05%, right < 0.01%, identical camera')

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
    # The laid metal is read from the solo picture without outlines or flash;
    # otherwise the dark outline counts as metal. The extent is the screen span
    # of everything that differs from the background.
    COWL, NACELLE = PIECES[3][1], PIECES[4][1]
    spans = {'cowl': [], 'nacelle': []}
    sheets = {'cowl': [], 'nacelle': []}
    for i in range(10):
        tt = round(20.2 + i * 0.1, 2)
        for name, ids in (('cowl', COWL), ('nacelle', NACELLE)):
            solo = ",".join(ids)
            pg = go(f'frame=opening&theme=light&solo={solo}&nolines=1&noflash=1&t={tt:.2f}', which=extra[0])
            path = f'{TMP}/c-{name}-{i}.png'
            pg.screenshot(path=path)
            sheets[name].append(path)
            px = pixels(path)
            xs = [x for y in range(100, 1080, 2) for x in range(0, 1280, 2) if far(px, x, y, 12)]
            spans[name].append((min(xs), max(xs)) if xs else None)
    fullspan = {}
    for name, ids in (('cowl', COWL), ('nacelle', NACELLE)):
        mp = go(f'frame=opening&theme=light&mask=part:{",".join(ids)}&t=21.10', which=extra[1])
        mp.screenshot(path=f'{TMP}/c-full-{name}.png')
        pm = pixels(f'{TMP}/c-full-{name}.png')
        xs = [x for y in range(100, 1080, 2) for x in range(0, 1280, 2) if max(pm[x, y]) < 245]
        fullspan[name] = (min(xs), max(xs)) if xs else None
    # Cowl grows from +x to -x (leftwards on screen), nacelle the other way.
    # Before s + 0.20 nothing is laid yet, so leading empty samples are skipped.
    ok33 = True
    detail = []
    for name in ('cowl', 'nacelle'):
        got = [g for g in spans[name]]
        while got and got[0] is None:
            got.pop(0)
        detail.append(f'{name} {spans[name][0]}->{spans[name][-1]} full {fullspan[name]}')
        if not got or fullspan[name] is None or any(g is None for g in got):
            ok33 = False; continue
        if name == 'cowl':
            grow = all(got[i + 1][0] <= got[i][0] + 2 for i in range(len(got) - 1))
        else:
            grow = all(got[i + 1][1] >= got[i][1] - 2 for i in range(len(got) - 1))
        cover = (got[-1][1] - got[-1][0]) >= 0.9 * (fullspan[name][1] - fullspan[name][0])
        ok33 = ok33 and grow and cover
    with open(f'{OUT}/m3-both-sides.json', 'w') as f:
        json.dump({'spans': spans, 'full': fullspan}, f)
    sheet = Image.new('RGB', (10 * 192, 2 * 162), '#ffffff')
    for r, name in enumerate(('cowl', 'nacelle')):
        for c, path in enumerate(sheets[name]):
            sheet.paste(Image.open(path).convert('RGB').resize((192, 162), Image.LANCZOS), (c * 192, r * 162))
    sheet.save(f'{OUT}/合拢.png')
    check('33 both sides close', ok33, '; '.join(detail), 'each side grows monotonically towards its end, full by 21.1')

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
        still = still and max(abs(a - b) for a, b in zip(pr['camera']['target'], p1['camera']['target'])) < 1e-6
    # Compare with the camera frame=net really renders with. Comparing with the
    # page's own fit() result would be the page agreeing with itself.
    net = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    net.add_init_script(THREE_PROBE)
    net.goto(f'{URL}?frame=net&theme=light')
    net.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
    time.sleep(0.5)
    netcam = net.evaluate("""async () => {
      const url = performance.getEntriesByType('resource').map(r => r.name).find(n => n.includes('deps/three'));
      const THREE = await import(url);
      const c = window.__lastCam;
      if (!c) return null;
      const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(c.quaternion);
      return { position: c.position.toArray(), dir: dir.toArray() };
    }""")
    net.close()
    dist = math.inf; angle = 180.0
    if netcam:
        dist = math.dist(p1['camera']['position'], netcam['position'])
        d = [p1['camera']['target'][i] - p1['camera']['position'][i] for i in range(3)]
        n = math.sqrt(sum(x * x for x in d)) or 1
        dot = sum((d[i] / n) * netcam['dir'][i] for i in range(3))
        angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
    go('frame=opening&theme=light&t=17.0')
    pos = []
    for i in range(int((21.9 - 17.0) * 60) + 1):
        page.evaluate(f'window.__seek({17.0 + i / 60})')
        pos.append(probe()['camera']['position'])
    steps = [math.dist(pos[i], pos[i + 1]) for i in range(len(pos) - 1)]
    jerks = [abs(steps[i + 1] - steps[i]) for i in range(len(steps) - 1)]
    med = sorted(steps)[len(steps) // 2]; medj = sorted(jerks)[len(jerks) // 2]
    ok35 = (still and dist <= 0.002 and angle <= 0.01 and netcam is not None
            and max(steps) <= 4 * max(med, 1e-9) and max(jerks) <= 4 * max(medj, 1e-9))
    check('35 camera', ok35,
          f'still {still}, net {netcam is not None}, position gap {dist:.4f}, direction {angle:.4f}deg, '
          f'step {max(steps):.4f}/{med:.4f}, jerk {max(jerks):.4f}/{medj:.4f}',
          'still after 21.9, within 0.002 and 0.01deg of frame=net, smooth')

    # ---- 35b assembled engine box (no threshold; the supervisor judges) ----
    page.evaluate('window.__seek(21.9)')
    page.screenshot(path=f'{TMP}/f35box.png')
    px = pixels(f'{TMP}/f35box.png')
    rows = [y for y in range(300, 1080)
            if sum(1 for x in range(0, 1280, 2) if max(abs(px[x, y][i] - BG[i]) for i in range(3)) > 18) >= 2]
    cols = [x for x in range(0, 1280)
            if sum(1 for y in range(300, 1080, 2) if max(abs(px[x, y][i] - BG[i]) for i in range(3)) > 18) >= 2]
    box = (min(cols), min(rows), max(cols), max(rows)) if rows and cols else None
    results.append({'check': '35b engine box', 'ok': True, 'value': f'{box} vs style (243, 330, 1051, 766)',
                    'expect': 'no threshold, for the supervisor'})
    print('INFO 35b engine box |', box, 'vs style (243, 330, 1051, 766)', flush=True)

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
    base37 = {}
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
        base37[name] = round(sum(pb[x, y][2] - pb[x, y][0] for (x, y) in pts) / len(pts), 1)
        if d < 10:
            bad37.append(f'{name} {d:+.0f}')
    go('frame=opening&theme=light&t=22.2')
    page.screenshot(path=f'{TMP}/e7-on.png')
    go('frame=opening&theme=light&t=22.2&noflash=1', which=extra[1])
    extra[1].screenshot(path=f'{TMP}/e7-off.png')
    pa = pixels(f'{TMP}/e7-on.png'); pb = pixels(f'{TMP}/e7-off.png')
    e7px = sum(1 for y in range(1080) for x in range(1280) if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 8)
    theory = {k: round(0.25 * (156 - v), 1) for k, v in base37.items()}
    with open(f'{OUT}/m3-flash-base.json', 'w') as f:
        json.dump({'base': base37, 'theory_peak': theory}, f, ensure_ascii=False, indent=2)
    fails = [b for b in bad37 if not b.endswith('empty')]
    extra37 = ''
    if fails:
        names = [b.split(' ')[0] for b in fails]
        extra37 = ' (base blue-red, theory peak ' + str([(n, base37.get(n), theory.get(n)) for n in names]) + ')'
    check('37 flash', not bad37 and e7px >= 20000,
          ('; '.join(bad37[:2]) + extra37) if bad37 else f'e7 {e7px}px',
          'each piece >= +10 blue-red, e7 >= 20,000 px')

    # ---- 38 rotor ----
    go('frame=opening&theme=light&t=22.0')
    r22 = probe()['rotor']
    def want_rotor(tt):
        # spin up 22.0-23.2, cruise to 26.0, ease out by 28.0, then hold 360.
        if tt <= 22.0:
            return 0.0
        if tt >= 28.0:
            return 360.0
        I = lambda u: u ** 6 - 3 * u ** 5 + 2.5 * u ** 4
        u = min(1, (tt - 22.0) / 1.2)
        cruise = max(0, min(tt, 26.0) - 23.2)
        ease = (tt - 26.0) - 2 * I((tt - 26.0) / 2) if tt > 26.0 else 0.0
        return (360 / 4.4) * (1.2 * I(u) + cruise + ease)

    bad38 = []
    for i in range(int((23.0 - 22.0) * 60) + 1):
        tt = 22.0 + i / 60
        page.evaluate(f'window.__seek({tt})')
        got = probe()['rotor']
        want = want_rotor(tt)
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
    # Counted at full resolution: the blades only turn 3.4 degrees by 22.5 s.
    fan_px = sum(1 for y in range(0, 1080) for x in range(0, 1280)
                 if max(pm[x, y]) < 245 and max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20)
    # The cowl region minus every rotor component: the fan and spinner seen
    # through the intake sit in front of the cowl wall and may change. The rotor
    # mask comes from one pose, so it is widened by 6 px to cover the tips that
    # sweep into the gap between blades and wall.
    rotor_ids = probe()['rotorIds']
    cowl_mask = go('frame=opening&theme=light&mask=part:fan-cowl.aft,fan-cowl.lip,fan-cowl.shell&t=22.5', which=extra[0])
    cowl_mask.screenshot(path=f'{TMP}/cowl-mask.png')
    rotor_mask = go(f'frame=opening&theme=light&mask=part:{",".join(rotor_ids)}&t=22.5', which=extra[0])
    rotor_mask.screenshot(path=f'{TMP}/rotor-mask.png')
    pm2 = pixels(f'{TMP}/cowl-mask.png')
    rot = Image.open(f'{TMP}/rotor-mask.png').convert('L').point(lambda v: 255 if v < 60 else 0)
    tight = rot.load()
    wide = rot.filter(ImageFilter.MaxFilter(13)).load()
    rest_tight = [(x, y) for y in range(1080) for x in range(1280) if max(pm2[x, y]) < 245 and tight[x, y] == 0]
    rest = [(x, y) for y in range(1080) for x in range(1280) if max(pm2[x, y]) < 245 and wide[x, y] == 0]
    moved = sum(1 for (x, y) in rest if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20)
    moved_tight = sum(1 for (x, y) in rest_tight if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20)
    cowl_share = moved / len(rest) if rest else 1.0
    share_tight = moved_tight / len(rest_tight) if rest_tight else 1.0
    ok38 = not bad38 and pure and fan_px >= 2000 and rest and cowl_share <= 0.01
    check('38 rotor', ok38,
          f'{bad38[:1]} pure {pure}, fan {fan_px}, cowl {moved}/{len(rest)} = {cowl_share*100:.2f}% '
          f'(exact rotor mask {moved_tight}/{len(rest_tight)} = {share_tight*100:.2f}%)',
          'rotor matches the formula, pure of t, fan turns, cowl region <= 1% moved')

    # ---- 39 no metal erased by the depth shells ----
    # The shells exist to hide a part's own back lines, so the picture to compare
    # against has the shells and the outlines both off: what shows there and not
    # in the real picture is metal the shell turned into background. (Hiding only
    # the shells also uncovers back lines, and those would count as metal.)
    bare = go('frame=opening&theme=light&t=9.6&noshells=1&nolines=1', which=extra[0])
    shellsonly = go('frame=opening&theme=light&t=9.6&noshells=1', which=extra[1])
    wiped = []
    for i in range(int((23.0 - 9.6) / 0.05) + 1):
        tt = round(9.6 + i * 0.05, 2)
        page.evaluate(f'window.__seek({tt})')
        bare.evaluate(f'window.__seek({tt})')
        page.screenshot(path=f'{TMP}/n39.png')
        bare.screenshot(path=f'{TMP}/b39.png')
        _, now_d = column(f'{TMP}/n39.png')
        _, bare_d = column(f'{TMP}/b39.png')
        n = ImageChops.multiply(now_d.point(lambda v: 255 if v < 15 else 0),
                                bare_d.point(lambda v: 255 if v > 40 else 0)).histogram()[255]
        wiped.append([tt, n])
    worst5 = sorted(wiped, key=lambda r: -r[1])[:5]
    # For the record: the same count with only the shells hidden, which also
    # shows the back lines the shells are there to hide.
    literal = []
    for tt in (12.78, 13.54, 17.85, 20.30):
        page.evaluate(f'window.__seek({tt})')
        shellsonly.evaluate(f'window.__seek({tt})')
        page.screenshot(path=f'{TMP}/n39.png')
        shellsonly.screenshot(path=f'{TMP}/b39.png')
        _, now_d = column(f'{TMP}/n39.png')
        _, bare_d = column(f'{TMP}/b39.png')
        n = ImageChops.multiply(now_d.point(lambda v: 255 if v < 15 else 0),
                                bare_d.point(lambda v: 255 if v > 40 else 0)).histogram()[255]
        literal.append([tt, n])
    with open(f'{OUT}/m3-wiped.json', 'w') as f:
        json.dump({'worst': worst5, 'frames': wiped, 'only_shells_hidden': literal}, f)
    check('39 no metal erased', all(n <= 150 for _, n in wiped),
          f'worst {worst5}; shells only {literal}', 'every frame <= 150 pixels of metal turned into background')

    check('14c console during milestone three', not console, console[:2] or 'none', 'no error / pageerror')
    browser.close()

with open(f'{OUT}/results.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} milestone-three checks passed')
sys.exit(0 if passed == len(results) else 1)
