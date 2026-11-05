"""Checks 29-39 for opening milestone three A, 40-48 and section 8 for three B."""
import json, math, os, sys, time
from PIL import Image, ImageFilter, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
ROOT = PROJECT_ROOT
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
    o.render = (scene, cam) => {
      window.__lastCam = cam; window.__scene = scene; window.__renderer = o;
      return orig(scene, cam);
    };
  }
});"""

# a15ba3a has no parameter for the depth shells, so they are switched off in the
# page and the scene is drawn once more.
HIDE_SHELLS = """() => {
  window.__scene.traverse(o => {
    const m = o.material;
    if (o.isMesh && m && m.colorWrite === false) o.visible = false;
  });
  window.__renderer.render(window.__scene, window.__lastCam);
}"""

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
    base3 = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    base3.add_init_script(THREE_PROBE)

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
    # The metal layer is the same on both sides once a15ba3a's depth shells are
    # switched off in the page: it has no parameter for that, so they are hidden
    # and the scene is drawn again. Then the normal-frame differences are split
    # into metal (the nolines pair changed there too) and line-only changes.
    rows29 = []
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
        go(f'frame=opening&theme=light&t={tt}&nolines=1')
        page.screenshot(path=f'{TMP}/m-now.png')
        base3.goto(f'{BASE_URL}?frame=opening&theme=light&t={tt}&nolines=1')
        base3.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.3)
        base3.screenshot(path=f'{TMP}/m-base-asis.png')
        base3.evaluate(HIDE_SHELLS)
        time.sleep(0.2)
        base3.screenshot(path=f'{TMP}/m-base.png')
        metal_share = share(f'{TMP}/m-now.png', f'{TMP}/m-base.png', (0, 0, 1280, 1080))
        now, _ = column(f'{TMP}/j-now.png')
        base, _ = column(f'{TMP}/j-base.png')
        nowm, _ = column(f'{TMP}/m-now.png')
        basem, _ = column(f'{TMP}/m-base.png')
        changed = ImageChops.difference(now, base).convert('L').point(lambda v: 255 if v > 8 else 0)
        # What the metal layer gained: the new build without outlines against
        # a15ba3a without outlines, shells still doing their erasing there.
        gained = column(f'{TMP}/m-base-asis.png')[0]
        metal = ImageChops.difference(nowm, gained).convert('L').point(lambda v: 255 if v > 8 else 0)
        line_only = ImageChops.subtract(changed, metal)
        line_share = line_only.histogram()[255] / (1280 * 1080)
        rows29.append([tt, round(metal_share * 100, 4), changed.histogram()[255],
                       metal.histogram()[255], round(line_share * 100, 4)])
        if metal_share > 0.0001: worst = (tt + ' metal', metal_share)
        if line_share > 0.0001: worst = (tt + ' lines', line_share)
    go('frame=opening&theme=light&t=17.0')
    cam_now = probe()['camera']
    go('frame=opening&theme=light&t=17.0', base=True)
    cam_base = probe()['camera']
    cam_ok = cam_ok and max(abs(x - y) for x, y in zip(cam_now['position'], cam_base['position'])) < 1e-6
    joined = (worst[1] < 0.0001 and cam_ok)
    check('29 join', joined,
          f'worst {worst[0]}s {worst[1]*100:.4f}%, camera {cam_ok}, rows {rows29}',
          '3.0/8.0 < 0.01%, metal layer < 0.01%, line-only < 0.01%, right < 0.01%, identical camera')

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
    # ======================= opening 3B: 40-48 and section 8 =======================
    OUT3B = f'{ROOT}/review/opening/m3b'
    os.makedirs(OUT3B, exist_ok=True)
    first3b = len(results)
    console3b = []
    for pg_ in [page, *extra]:
        pg_.on('console', lambda m: console3b.append(m.text) if m.type == 'error' else None)
        pg_.on('pageerror', lambda e: console3b.append(f'pageerror: {e}'))
    LEFT, RIGHT, FULL = (0, 0, 1280, 1080), (1280, 0, 1920, 1080), (0, 0, 1920, 1080)

    def snap(pg, name):
        pg.screenshot(path=f'{TMP}/{name}.png')
        return Image.open(f'{TMP}/{name}.png').convert('RGB')

    def over(a, b, box, tol=8, keep=None):
        """Pixels in box where any channel differs by more than tol."""
        d = ImageChops.difference(a.crop(box), b.crop(box))
        m = Image.merge('RGB', [c.point(lambda v, tol=tol: 255 if v > tol else 0) for c in d.split()]).convert('L')
        m = m.point(lambda v: 255 if v else 0)
        if keep is not None:
            m = ImageChops.multiply(m, keep)
        return m.histogram()[255]

    CAM_JS = """async () => {
      const url = performance.getEntriesByType('resource').map(r => r.name).find(n => n.includes('deps/three'));
      const THREE = await import(url);
      const c = window.__lastCam;
      if (!c) return null;
      const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(c.quaternion);
      return { position: c.position.toArray(), dir: dir.toArray() };
    }"""
    refpg = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    refpg.add_init_script(THREE_PROBE)
    refpg.on('console', lambda m: console3b.append(m.text) if m.type == 'error' else None)
    refpg.on('pageerror', lambda e: console3b.append(f'pageerror: {e}'))

    def reference(frame):
        refpg.goto(f'{URL}?frame={frame}&theme=light')
        refpg.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.5)
        return snap(refpg, f'ref-{frame}'), refpg.evaluate(CAM_JS)

    def against(tt, im_ref, cam_ref):
        go(f'frame=opening&theme=light&t={tt}')
        im = snap(page, f'vs-{tt}')
        pr = probe()
        left = over(im, im_ref, LEFT) / (1280 * 1080)
        right = over(im, im_ref, RIGHT) / (640 * 1080)
        dist = math.dist(pr['camera']['position'], cam_ref['position'])
        d = [pr['camera']['target'][i] - pr['camera']['position'][i] for i in range(3)]
        n = math.sqrt(sum(x * x for x in d)) or 1
        dot = sum((d[i] / n) * cam_ref['dir'][i] for i in range(3))
        angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        ok = left < 0.0001 and right < 0.0001 and dist <= 0.002 and angle <= 0.01
        return ok, f'{tt}s left {left*100:.4f}% right {right*100:.4f}% cam {dist:.5f} {angle:.5f}deg'

    # ---- 40 at 28.0 the picture is frame=net ----
    net_im, net_cam = reference('net')
    ok40, v40 = against(28.0, net_im, net_cam)
    check('40 28.0 = frame=net', ok40, v40, 'left and right < 0.01% over 8, camera within 0.002 and 0.01deg')

    # ---- 41 from 29.5 the picture is frame=net-end ----
    end_im, end_cam = reference('net-end')
    rows41 = [against(tt, end_im, end_cam) for tt in (29.5, 29.75, 30.0)]
    check('41 29.5-30.0 = frame=net-end', all(r[0] for r in rows41), '; '.join(r[1] for r in rows41),
          'each < 0.01% over 8, camera within 0.002 and 0.01deg')

    # ---- 42 every frame depends on t only ----
    # Besides the screenshot, the exact state: the 3D canvas's own pixels and the
    # markup of every overlay. Chrome rasterises the SVG column with a +-1 jitter
    # now and then even when nothing changed, so a screenshot alone can differ
    # without the frame depending on where the playhead came from.
    STATE_JS = """async () => {
      const parts = [document.querySelector('#model').toDataURL()];
      for (const sel of ['#graph', '#callouts', '#callout-labels', '.col-model .model-caption']) {
        const el = document.querySelector(sel); parts.push(el ? el.outerHTML : '');
      }
      const out = [];
      for (const p of parts) {
        const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(p));
        out.push([...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16));
      }
      return out;
    }"""
    bad42, notes42 = [], []
    for tt in (24.0, 25.0, 26.5, 27.7, 28.3, 29.0):
        go(f'frame=opening&theme=light&t={tt}')
        direct = snap(page, 'p42a')
        state_a = page.evaluate(STATE_JS)
        page.evaluate('window.__seek(29.9)')
        page.evaluate(f'window.__seek({tt})')
        time.sleep(0.2)
        back = snap(page, 'p42b')
        state_b = page.evaluate(STATE_JS)
        n = over(direct, back, FULL, tol=0)
        n1 = over(direct, back, FULL, tol=1)
        if state_a != state_b or n1:
            bad42.append(f'{tt}s state {state_a == state_b}, {n}px')
        elif n:
            notes42.append(f'{tt}s {n}px at 1 level, same state')
    check('42 pure of t', not bad42, '; '.join(bad42 + notes42) or 'all six identical',
          'seek 29.9 and back = direct open: same canvas pixels and markup, screenshot 0 px over 1 level')

    # ---- 43 graph timetable, read from the drawn page ----
    NODE_PLAN = {'e3': 23.0, 'design': 23.4, 'drill': 23.48, 'std': 23.56, 'mwo': 23.8, 'spray': 23.88, 'awo': 23.96,
                 'insp': 24.2, 'coat': 24.28, 'po': 24.6, 'powder': 24.68, 'supplier': 24.76, 'stock': 24.84}
    NODE_FADE = {k: (0.4 if k == 'e3' else 0.3) for k in NODE_PLAN}
    EDGE_PLAN = [('design', 'blade', 25.0, 25.35), ('coat', 'powder', 25.2, 25.55), ('drill', 'blade', 25.4, 25.75),
                 ('powder', 'spray', 25.6, 25.95), ('std', 'blade', 25.8, 26.15), ('awo', 'e7', 26.0, 26.35),
                 ('mwo', 'blade', 26.2, 26.55), ('powder', 'supplier', 26.4, 26.75), ('spray', 'blade', 26.6, 26.95),
                 ('insp', 'blade', 26.8, 27.15), ('blade', 'e3', 27.0, 27.35), ('po', 'blade', 27.2, 27.55),
                 ('po', 'm-comb', 27.3, 27.65), ('stock', 'blade', 27.6, 28.6), ('po', 'supplier', 28.0, 28.6)]
    GRAPH_JS = """() => {
      const g = document.querySelector('#graph');
      const nodes = {}, at = {};
      g.querySelectorAll('[data-node]').forEach(n => {
        nodes[n.dataset.node] = parseFloat(n.style.opacity || '1');
        const c = n.querySelector('circle'); at[n.dataset.node] = [+c.getAttribute('cx'), +c.getAttribute('cy')];
      });
      const draws = {}, starts = {};
      g.querySelectorAll('[data-draw]').forEach(p => {
        const [a, b] = p.getAttribute('stroke-dasharray').split(' ').map(Number);
        draws[p.dataset.draw] = a / b;
        const s = p.getPointAtLength(0); starts[p.dataset.draw] = [s.x, s.y];
      });
      const heads = [...g.querySelectorAll('[data-head]')].map(c => c.dataset.head);
      const rest = [...g.querySelectorAll('[data-edge]')].map(p => p.dataset.edge);
      const counter = [...g.querySelectorAll('text')].map(t => t.textContent).find(x => x.includes('个节点'));
      return { nodes, at, draws, starts, heads, rest, counter };
    }"""
    FPS = 60
    go('frame=opening&theme=light&t=22.9')
    seen_node, full_node, seen_edge, done_edge, wrong_dir = {}, {}, {}, {}, set()
    for i in range(int(round(22.9 * FPS)), int(round(29.0 * FPS)) + 1):
        tt = i / FPS
        page.evaluate(f'window.__seek({tt})')
        s = page.evaluate(GRAPH_JS)
        for node in NODE_PLAN:
            o = s['nodes'].get(node)
            if o is not None and o > 0 and node not in seen_node: seen_node[node] = tt
            if o is not None and o >= 1 and node not in full_node: full_node[node] = tt
        for a, b, _, _ in EDGE_PLAN:
            key = f'{a}>{b}'
            drawn = key in s['draws'] or key in s['rest']
            if drawn and key not in seen_edge:
                seen_edge[key] = tt
                st = s['starts'].get(key); src = s['at'].get(a)
                if st and src and math.dist(st, src) > 1.0: wrong_dir.add(key)
            whole = (key in s['rest'] or s['draws'].get(key, 0) >= 0.9999) and key not in s['heads']
            if whole and key not in done_edge: done_edge[key] = tt
    frame = 1 / FPS + 1e-6
    late = []
    for node, start in NODE_PLAN.items():
        if abs(seen_node.get(node, 99) - start) > frame: late.append(f'{node} in {seen_node.get(node)}')
        if abs(full_node.get(node, 99) - (start + NODE_FADE[node])) > frame: late.append(f'{node} full {full_node.get(node)}')
    for a, b, start, end in EDGE_PLAN:
        key = f'{a}>{b}'
        if abs(seen_edge.get(key, 99) - start) > frame: late.append(f'{key} start {seen_edge.get(key)}')
        if abs(done_edge.get(key, 99) - end) > frame: late.append(f'{key} end {done_edge.get(key)}')
    page.evaluate('window.__seek(28.0)')
    s28 = page.evaluate(GRAPH_JS)
    done28 = len(s28['rest']) + sum(1 for k, v in s28['draws'].items() if v >= 0.9999 and k not in s28['heads'])
    stock28 = s28['draws'].get('stock>blade', -1)
    page.evaluate('window.__seek(30.0)')
    s30 = page.evaluate(GRAPH_JS)
    done30 = len(s30['rest']) + sum(1 for k, v in s30['draws'].items() if v >= 0.9999 and k not in s30['heads'])
    ok43 = (not late and not wrong_dir and done28 == 33 and abs(stock28 - 0.42) <= 0.005 and done30 == 35
            and s28['counter'] == '34 个节点 · 33 / 35 条关系' and s30['counter'] == '34 个节点 · 35 条关系')
    check('43 graph timetable', ok43,
          f"{len(late)} off the table {late[:3]}, wrong direction {sorted(wrong_dir)}, 28.0: {done28} done, "
          f"stock {stock28:.4f}, '{s28['counter']}'; 30.0: {done30} done, '{s30['counter']}'",
          'every fade-in, start and end within a frame; 33 done and stock 0.42 at 28.0; 35 at 30.0')

    # ---- 44 flashes where a line lands on a product node ----
    def blue_red(im, pts):
        px = im.load()
        return sum(px[x, y][2] - px[x, y][0] for x, y in pts) / max(1, len(pts))

    def region(mask_im, off_im, box=LEFT):
        pm, po = mask_im.load(), off_im.load()
        return [(x, y) for y in range(box[1], box[3], 2) for x in range(box[0], box[2], 2)
                if (pm is None or max(pm[x, y]) < 245) and max(abs(po[x, y][i] - BG[i]) for i in range(3)) > 12]

    RING_ID = 'turbine.stage-1-blades'
    rows44, bad44 = [], []
    for a, b, start, end in EDGE_PLAN:
        if b != 'blade':
            continue
        tt = end + 0.2
        mk = snap(go(f'frame=opening&theme=light&mask=part:{RING_ID}&t={tt:.3f}', which=extra[0]), 'm44')
        on = snap(go(f'frame=opening&theme=light&solo={RING_ID}&t={tt:.3f}', which=page), 'o44')
        off = snap(go(f'frame=opening&theme=light&solo={RING_ID}&noflash=1&t={tt:.3f}', which=extra[1]), 'f44')
        pts = region(mk, off)
        d = blue_red(on, pts) - blue_red(off, pts) if pts else 0
        rows44.append(f'{a}>{b} ring {d:+.0f}')
        if d < 10: bad44.append(rows44[-1])
    # Engine seven: the whole engine at 15 %, at the peak of its half second.
    for a, b, start, end in EDGE_PLAN:
        if b != 'e7':
            continue
        tt = end + 0.25
        on = snap(go(f'frame=opening&theme=light&t={tt:.3f}', which=page), 'o44')
        off = snap(go(f'frame=opening&theme=light&noflash=1&t={tt:.3f}', which=extra[1]), 'f44')
        pts = [(x, y) for y in range(100, 1080, 2) for x in range(0, 1280, 2)
               if max(abs(off.load()[x, y][i] - BG[i]) for i in range(3)) > 12]
        d = blue_red(on, pts) - blue_red(off, pts)
        rows44.append(f'{a}>{b} engine {d:+.0f}')
        if d < 10: bad44.append(rows44[-1])
    # The combustor takes the highlight instead: before 27.3 against 28.0.
    COMB = 'combustor.cans,combustor.casing,combustor.injectors,combustor.inner-shell'
    mk = snap(go(f'frame=opening&theme=light&mask=part:{COMB}&t=28.0', which=extra[0]), 'm44')
    before = snap(go(f'frame=opening&theme=light&solo={COMB}&noflow=1&t=27.3', which=page), 'o44')
    after = snap(go(f'frame=opening&theme=light&solo={COMB}&noflow=1&t=28.0', which=extra[1]), 'f44')
    pts = region(mk, after)
    d = blue_red(after, pts) - blue_red(before, pts)
    rows44.append(f'po>m-comb highlight {d:+.0f}')
    if d < 10: bad44.append(rows44[-1])
    check('44 flashes', not bad44, '; '.join(rows44), 'each landing >= +10 blue-red (ring 25 %, engine 15 %, combustor highlight)')

    # ---- 45 steady while the shells fade and open ----
    rotor_ids = probe()['rotorIds']
    fm = snap(go('frame=opening&theme=light&mask=flow&t=25.0', which=extra[1]), 'flowmask')
    flow_mask = fm.crop(LEFT).convert('L').point(lambda v: 255 if v < 128 else 0)
    main = go('frame=opening&theme=light&t=23.0', which=page)
    rmask = go(f'frame=opening&theme=light&mask=part:{",".join(rotor_ids)}&t=23.0', which=extra[0])

    def at(pg, tt, name):
        pg.evaluate(f'window.__seek({tt})')
        return snap(pg, name).crop(LEFT)
    prev = at(main, 23.0, 's45'); prot = at(rmask, 23.0, 'r45').convert('L').point(lambda v: 255 if v < 128 else 0)
    rows45 = []
    for i in range(1, 61):
        tt = round(23.0 + 0.05 * i, 3)
        cur = at(main, tt, 's45'); crot = at(rmask, tt, 'r45').convert('L').point(lambda v: 255 if v < 128 else 0)
        keep = ImageChops.lighter(ImageChops.lighter(prot, crot), flow_mask).filter(ImageFilter.MaxFilter(9)).point(lambda v: 0 if v else 255)
        d = ImageChops.difference(prev, cur)
        kept = keep.histogram()[255]
        mean = sum(ImageStat.Stat(ImageChops.multiply(d, Image.merge('RGB', [keep] * 3))).sum) / 3 / max(1, kept)
        big = over(prev, cur, (0, 0, 1280, 1080), tol=60, keep=keep)
        rows45.append((tt, round(mean, 3), big))
        prev, prot = cur, crot
    worst_mean = max(rows45, key=lambda r: r[1]); worst_big = max(rows45, key=lambda r: r[2])
    # The depth-write (0.6) and shadow (0.5) switches, frame by frame, rotor and flow off.
    sw = go('frame=opening&theme=light&norotor=1&noflow=1&t=23.70', which=extra[1])
    seq = []
    prevs = None
    for i in range(0, 19):
        tt = round(23.70 + i / 60, 4)
        sw.evaluate(f'window.__seek({tt})')
        g = sw.evaluate('window.__openingProbe().m3b.ghost')
        cur = snap(sw, 'w45').crop(LEFT)
        if prevs is not None:
            seq.append((tt, g, over(prevs[1], cur, (0, 0, 1280, 1080), tol=30), prevs[0]))
        prevs = (g, cur)
    straddle = [r for r in seq if (r[3] < 0.5 <= r[1]) or (r[3] < 0.6 <= r[1])]
    others = sorted(r[2] for r in seq if r not in straddle)
    med = others[len(others) // 2] if others else 0
    jump = max((r[2] for r in straddle), default=0)
    ok45 = worst_mean[1] <= 4 and worst_big[2] < 3000 and straddle and jump <= max(3 * med, 200)
    with open(f'{OUT3B}/m3b-steady.json', 'w') as f:
        json.dump({'frames': rows45, 'switch': seq}, f)
    check('45 steady', ok45,
          f'worst mean {worst_mean[1]} at {worst_mean[0]}s, worst >60 {worst_big[2]}px at {worst_big[0]}s; '
          f'switch frames {[(r[0], r[2]) for r in straddle]} vs median {med}px over 30',
          'mean <= 4, < 3,000 px over 60 per 0.05 s; no jump at the 0.5 and 0.6 switches')

    # ---- 46 every part on screen ----
    parts46 = []
    for tt in range(23, 31):
        page.evaluate(f'window.__seek({tt})')
        pr = probe()
        parts46.append((tt, pr['partsVisible'], pr['visibleParts']))
    check('46 parts', all(a == 2027 and b == 2027 for _, a, b in parts46),
          ', '.join(f'{t}s {a}' for t, a, _ in parts46), '2,027 visible parts every second 23-30')

    # ---- 47 airflow ----
    fm_keep = flow_mask
    on = snap(go('frame=opening&theme=light&t=25.0', which=page), 'o47')
    off = snap(go('frame=opening&theme=light&noflow=1&t=25.0', which=extra[0]), 'f47')
    n25 = over(on, off, LEFT, tol=15, keep=fm_keep)
    on28 = snap(go('frame=opening&theme=light&t=28.0', which=page), 'o47')
    off28 = snap(go('frame=opening&theme=light&noflow=1&t=28.0', which=extra[0]), 'f47')
    n28 = over(on28, off28, LEFT, tol=0)
    go('frame=opening&theme=light&t=25.0', which=page)
    direct = snap(page, 'p47a')
    state_a = page.evaluate(STATE_JS)
    page.evaluate('window.__seek(27.9)'); page.evaluate('window.__seek(25.0)'); time.sleep(0.2)
    back = snap(page, 'p47b')
    state_b = page.evaluate(STATE_JS)
    # Same judgement as item 42: exact canvas and markup, screenshot within one level.
    nback = over(direct, back, FULL, tol=0)
    nback1 = over(direct, back, FULL, tol=1)
    same = state_a == state_b and nback1 == 0
    check('47 airflow', n25 >= 3000 and n28 == 0 and same,
          f'25.0 {n25}px over 15 in the flow region, 28.0 {n28}px, 27.9->25.0 state {state_a == state_b}, '
          f'{nback}px at 1 level, {nback1}px over 1',
          '>= 3,000 at 25.0, 0 at 28.0, seek back identical')

    # ---- 49 flow lines never cross a solid part (cross-section test) ----
    # Every drawn segment is cut into 0.02-wide axial slices; the radii it covers
    # in a slice may not fall inside the radius range of any visible part that
    # is solid and overlaps that slice (tolerance 0.005). Shell parts count as
    # solid until they are fully ghosted.
    PARTS49 = json.load(open(f'{ROOT}/.claude/worktrees/style-frames/public/models/turbofan-parts.json'))['parts']
    GHOST_MODULES = ('nacelle', 'fan-cowl', 'core-casing')
    W49, TOL49 = 0.02, 0.005

    def slices(seg):
        x0, r0, x1, r1 = seg
        if x0 > x1: x0, r0, x1, r1 = x1, r1, x0, r0
        cuts = [x0] + [k * W49 for k in range(math.floor(x0 / W49) + 1, math.ceil(x1 / W49))] + [x1]
        for a, b in zip(cuts, cuts[1:]):
            if b - a < 1e-9: continue
            ra = r0 + (r1 - r0) * (a - x0) / (x1 - x0); rb = r0 + (r1 - r0) * (b - x0) / (x1 - x0)
            yield math.floor((a + b) / 2 / W49), min(ra, rb), max(ra, rb)

    go('frame=opening&theme=light&t=22.0')
    hits49, tested49, empty49 = [], 0, []
    for i in range(1, 60):
        tt = round(22.0 + 0.1 * i, 2)
        page.evaluate(f'window.__seek({tt})')
        g = page.evaluate('window.__flowGeometry()')
        vis = set(g['visible'])
        solid = [p for p in PARTS49 if p['id'] in vis and not (p['module'] in GHOST_MODULES and g['ghost'] >= 0.999)]
        if not g['segments']: empty49.append(tt)
        for fam, segs in g['segments'].items():
            for seg in segs:
                for k, lo, hi in slices(seg):
                    tested49 += 1
                    sx0, sx1 = k * W49, (k + 1) * W49
                    for p in solid:
                        if (p['axial'][1] >= sx0 and p['axial'][0] <= sx1
                                and lo <= p['radius'][1] + TOL49 and hi >= p['radius'][0] - TOL49):
                            hits49.append(f'{tt}s {fam} x {sx0:.2f} r {lo:.3f} {p["id"]}'); break
    # Inside the bypass duct (0.2 < x < 1.3): free radii below the duct and cowl
    # walls that no solid part covers, slice by slice. A line can only run there
    # if one radius stays free in every slice.
    duct = []
    for k in range(10, 65):
        sx0, sx1 = k * W49, (k + 1) * W49
        here = [p for p in PARTS49 if p['axial'][0] <= sx1 and p['axial'][1] >= sx0]
        wall = min((p['radius'][0] for p in here if p['module'] in ('nacelle', 'fan-cowl')), default=None)
        if wall is None: continue
        blocks = sorted((p['radius'][0] - TOL49, p['radius'][1] + TOL49) for p in here if p['module'] not in GHOST_MODULES)
        free, cur = [], 0.0
        for a, b in blocks:
            if a > cur: free.append((cur, min(a, wall)))
            cur = max(cur, b)
        if cur < wall: free.append((cur, wall))
        duct.append((round(sx0, 2), [(round(a, 3), round(b, 3)) for a, b in free if b > a and a > 0.1]))
    closed = [x for x, f in duct if not f]
    with open(f'{OUT3B}/m3b-flow-section.json', 'w') as f:
        json.dump({'hits': hits49, 'tested': tested49, 'duct_free': duct}, f, ensure_ascii=False, indent=1)
    check('49 flow cross-section', not hits49 and not empty49 and tested49 > 0,
          f'{tested49} slice pieces at 59 times, {len(hits49)} inside a solid part {hits49[:2]}; '
          f'duct 0.2-1.3: {len(closed)} of {len(duct)} slices have no free radius (from {closed[0] if closed else None}), so no line inside',
          'no flow piece within 0.005 of a visible solid part in its 0.02 slice')

    # ---- 8 one pass from 23.0 on, and 22.0-23.0 as before ----
    go('frame=opening&theme=light&t=23.0')
    twos = []
    for i in range(int(round(23.0 * 60)), int(round(30.0 * 60)) + 1):
        page.evaluate(f'window.__seek({i / 60})')
        if page.evaluate('window.__openingProbe().passes') != 1: twos.append(round(i / 60, 3))
    check('8a one pass 23-30', not twos, f'{len(twos)} frames with two passes {twos[:3]}', 'passes = 1 on every frame')
    worst8 = (0, 0.0)
    for i in range(11):
        tt = round(22.0 + 0.1 * i, 2)
        a = snap(go(f'frame=opening&theme=light&noflow=1&t={tt}', which=page), 'n8')
        b = snap(go(f'frame=opening&theme=light&t={tt}', base=True, which=extra[0]), 'b8')
        s = over(a, b, FULL) / (1920 * 1080)
        if s >= worst8[1]: worst8 = (tt, s)
    check('8b 22-23 vs two passes', worst8[1] < 0.0001, f'worst {worst8[1]*100:.4f}% at {worst8[0]}s', '< 0.01% over 8 against af3ce3e')

    check('48 console', not console3b and not console, (console3b + console)[:2] or 'none', 'no error / pageerror')
    refpg.close()
    with open(f'{OUT3B}/results.json', 'w') as f:
        json.dump(results[first3b:], f, ensure_ascii=False, indent=2)
    browser.close()

# Three A keeps its own file; three B's items are in m3b/results.json.
with open(f'{OUT}/results.json', 'w') as f:
    json.dump([r for r in results if r['check'].split(' ')[0] < '40' or r['check'].startswith(('14c', '35b'))], f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} milestone-three checks passed')
sys.exit(0 if passed == len(results) else 1)
