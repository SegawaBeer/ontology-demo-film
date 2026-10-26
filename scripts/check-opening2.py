"""Checks 18-25 for opening milestone two; appends to review/opening/results.json."""
import json, math, os, sys, time
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
OUT = f'{ROOT}/review/opening'
URL = 'http://127.0.0.1:5192/frames.html'
BASE_URL = 'http://127.0.0.1:5193/frames.html'
BG = (238, 240, 238)
TMP = '/tmp/opening-check2'
os.makedirs(TMP, exist_ok=True)

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

STAGE = [
    (['turbine.stage-2-blades', 'turbine.stage-2-hub', 'turbine.stage-2-outer', 'turbine.stage-2-tip-ring', 'turbine.stage-1-outer', 'turbine.stage-1-tip-ring'], 10.10, 'c-t2'),
    (['turbine.stage-3-blades', 'turbine.stage-3-hub', 'turbine.stage-3-outer', 'turbine.stage-3-tip-ring'], 10.70, 'c-t3'),
    (['turbine.stage-4-blades', 'turbine.stage-4-outer', 'turbine.stage-4-tip-ring'], 11.30, 'c-t4'),
    (['turbine.stage-5-blades', 'turbine.stage-5-hub', 'turbine.stage-5-outer', 'turbine.stage-5-tip-ring'], 11.90, 'c-t5'),
]
COMP = ['compressor.stage-4', 'compressor.stators', 'compressor.stage-3', 'compressor.struts',
        'compressor.stage-2', 'compressor.stage-1', 'compressor.drum', 'compressor.inlet-bell']
compStart = lambda i: 13.50 + 2.40 * (i / 7) ** 0.7

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
        time.sleep(0.35)
        return pg

    def probe():
        return page.evaluate('window.__openingProbe()')

    # ---- 18 join at 9.6 ----
    a = f'{TMP}/join-now.png'
    go('frame=opening&theme=light&t=9.6')
    page.screenshot(path=a)
    box = page.evaluate("""() => {
      const paths = [...document.querySelectorAll('#graph path')].filter(p => p.getAttribute('stroke') === 'var(--lit)');
      if (!paths.length) return [0, 0, 0, 0];
      const rects = paths.map(p => p.getBoundingClientRect());
      return [Math.min(...rects.map(r => r.left)) - 4, Math.min(...rects.map(r => r.top)) - 4,
              Math.max(...rects.map(r => r.right)) + 4, Math.max(...rects.map(r => r.bottom)) + 4];
    }""")
    cam_now = probe()['camera']
    b = f'{TMP}/join-base.png'
    go('frame=opening&theme=light&t=9.6', base=True)
    page.screenshot(path=b)
    cam_base = probe()['camera']
    left = share(a, b, (0, 0, 1280, 1080))
    pa, pb = pixels(a), pixels(b)
    outside = 0
    for y in range(1080):
        for x in range(1280, 1920):
            ca, cb = pa[x, y], pb[x, y]
            if max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2])) > 8:
                if not (box[0] - 1 <= x <= box[2] + 1 and box[1] - 1 <= y <= box[3] + 1):
                    outside += 1
    cam_same = max(abs(x - y) for x, y in zip(cam_now['position'], cam_base['position'])) < 1e-6
    check('18 join at 9.6', left < 0.0001 and outside == 0 and cam_same,
          f'left {left*100:.4f}%, right outside edge box {outside}px, camera same {cam_same}',
          'left < 0.01%, right only around the edge, identical camera')

    # ---- 19 parts arrive ----
    schedule = {}
    for ids, start, _ in STAGE:
        for cid in ids:
            schedule[cid] = start
    schedule['shaft.main'] = 12.70
    for i, cid in enumerate(COMP):
        schedule[cid] = compStart(i)
    go('frame=opening&theme=light&t=9.6')
    firsts = {}
    for i in range(int((17.0 - 9.6) * 60) + 1):
        tt = 9.6 + i / 60
        page.evaluate(f'window.__seek({tt})')
        comps = probe()['components']
        for cid in schedule:
            if cid not in firsts and comps.get(cid):
                firsts[cid] = tt
    late = [(c, firsts.get(c), s) for c, s in schedule.items() if firsts.get(c) is None or abs(firsts[c] - s) > 1 / 60 + 1e-6]
    go('frame=opening&theme=light&t=17.0')
    parts = probe()['visibleParts']
    check('19 parts arrive', not late and parts == 1406, f'{len(late)} mismatches, visible parts {parts}',
          'schedule within a frame, 1406 parts')

    # ---- 20 outline first, measured on the real picture ----
    cats = [(f'stage{i + 2}', ids, start, 0.55, 0.10, 0.20) for i, (ids, start, _) in enumerate(STAGE)]
    cats += [('shaft', ['shaft.main'], 12.70, 1.00, 0.10, 0.25),
             ('comp4', ['compressor.stage-4'], compStart(0), 0.40, 0.08, 0.14),
             ('stators', ['compressor.stators'], compStart(1), 0.40, 0.08, 0.14),
             ('comp1', ['compressor.stage-1'], compStart(5), 0.40, 0.08, 0.14),
             ('drum', ['compressor.drum'], compStart(6), 0.40, 0.08, 0.14)]
    curves = {}
    problems = []
    for name, ids, start, sweep_to, o0, o1 in cats:
        solo = ",".join(ids)
        mp = go(f'frame=opening&theme=light&mask=part:{solo}&t={start:.3f}', which=extra[0])
        mp.screenshot(path=f'{TMP}/m-{name}.png')
        normal = go(f'frame=opening&theme=light&t={start:.3f}', which=page)
        lines = go(f'frame=opening&theme=light&nolines=1&t={start:.3f}', which=extra[1])
        times = [start - 0.05 + k / 60 for k in range(int((sweep_to + 0.10) * 60) + 1)]
        gs, os_ = [], []
        for tt in times:
            for pg in (normal, lines, mp):
                pg.evaluate(f'window.__seek({tt:.4f})')
            page.screenshot(path=f'{TMP}/n-{name}.png')
            extra[1].screenshot(path=f'{TMP}/l-{name}.png')
            mp.screenshot(path=f'{TMP}/mk-{name}.png')
            pn = pixels(f'{TMP}/n-{name}.png'); pl = pixels(f'{TMP}/l-{name}.png'); pm = pixels(f'{TMP}/mk-{name}.png')
            pts = [(x, y) for y in range(0, 1080, 2) for x in range(0, 1280, 2) if pm[x, y][0] < 60]
            if not pts:
                continue
            g = sum(1 for p in pts if far(pl, p[0], p[1])) / len(pts)
            o = sum(1 for p in pts if max(abs(pn[p[0], p[1]][i] - pl[p[0], p[1]][i]) for i in range(3)) > 20) / len(pts)
            gs.append(g); os_.append(o); curves.setdefault(name, []).append([round(tt, 3), round(g, 4), round(o, 4)])
        idx0 = int((o0 + 0.05) * 60)
        idx1 = int((o1 + 0.05) * 60)
        win_g = gs[idx0:idx1 + 1]; win_o = os_[idx0:idx1 + 1]
        if not win_o or min(win_o) < 0.04:
            problems.append(f'{name} outline {min(win_o)*100 if win_o else 0:.0f}%')
        if not win_g or max(win_g) >= 0.05:
            problems.append(f'{name} metal early {max(win_g)*100 if win_g else 0:.0f}%')
        for i in range(idx1 + 1, len(gs)):
            if gs[i] < gs[i - 1] - 0.02:
                problems.append(f'{name} drops')
                break
        if gs and gs[-1] <= 0.6:
            problems.append(f'{name} ends {gs[-1]*100:.0f}%')
    with open(f'{OUT}/m2-curves.json', 'w') as f:
        json.dump(curves, f)
    check('20 outline before metal', not problems,
          '; '.join(problems[:3]) if problems else 'outline windows show only lines; metal rises; finishes above 60%',
          'outline window O >= 4% and G < 5%, G non-decreasing, ends > 60%')

    # ---- 21 stays in frame ----
    worst = (999, 0)
    go('frame=opening&theme=light&mask=1&t=9.6')
    for i in range(int((17.0 - 9.6) / 0.1) + 1):
        tt = 9.6 + i * 0.1
        page.evaluate(f'window.__seek({tt})')
        page.screenshot(path=f'{TMP}/frame.png')
        px = Image.open(f'{TMP}/frame.png').convert('L').load()
        minx, miny, maxx, maxy = 1280, 1080, 0, 0
        for y in range(1080):
            for x in range(1280):
                if px[x, y] < 60:
                    if x < minx: minx = x
                    if x > maxx: maxx = x
                    if y < miny: miny = y
                    if y > maxy: maxy = y
        edge = min(minx, miny, 1280 - maxx, 1080 - maxy)
        if edge < worst[0]:
            worst = (edge, round(tt, 1))
    check('21 stays in frame', worst[0] >= 24, f'worst {worst[0]}px at {worst[1]}s', '>= 24px from every edge')

    # ---- 22 camera ----
    go('frame=opening&theme=light&t=17.0')
    pr = probe()
    cp, ct = pr['camera']['position'], pr['camera']['target']
    d = [cp[i] - ct[i] for i in range(3)]
    n = math.sqrt(sum(v * v for v in d)); d = [v / n for v in d]
    tgt = [0.62, 0.27, 0.73]; tn = math.sqrt(sum(v * v for v in tgt)); tgt = [v / tn for v in tgt]
    angle = math.degrees(math.acos(max(-1, min(1, sum(a * b for a, b in zip(d, tgt))))))
    go('frame=opening&theme=light&t=9.6')
    pos = []
    for i in range(int((17.0 - 9.6) * 60) + 1):
        page.evaluate(f'window.__seek({9.6 + i / 60})')
        pos.append(probe()['camera']['position'])
    steps = [math.dist(pos[i], pos[i + 1]) for i in range(len(pos) - 1)]
    jerks = [abs(steps[i + 1] - steps[i]) for i in range(len(steps) - 1)]
    med = sorted(steps)[len(steps) // 2]; medj = sorted(jerks)[len(jerks) // 2]
    ok22 = angle <= 1 and max(steps) <= 4 * max(med, 1e-9) and max(jerks) <= 4 * max(medj, 1e-9)
    check('22 camera', ok22, f'angle {angle:.2f}deg, step {max(steps):.4f}/{med:.4f}, jerk {max(jerks):.4f}/{medj:.4f}',
          'angle <= 1deg, steps and jerks <= 4x median')

    # ---- 23 graph ----
    go('frame=opening&theme=light&t=17.0')
    g = probe()['graph']
    texts = ' '.join(g['texts'])
    edges = page.evaluate("() => [...document.querySelectorAll('#graph path')].filter(p => p.getAttribute('stroke') === 'var(--lit)').length")
    ok23 = (g['nodes'] == 13 and g['counter'] == '13 个节点 · 10 条关系' and edges == 10
            and not any(k in texts for k in ('转子', '7 号发动机', '研发', '生产', '质量', '供应链')))
    node_times = {'c-t2': 10.10, 'c-t3': 10.70, 'c-t4': 11.30, 'c-t5': 11.90, 'm-turb': 12.60,
                  'm-shaft': 12.70, 'c-comp4': compStart(0), 'c-comp3': compStart(2),
                  'c-comp2': compStart(4), 'c-comp1': compStart(5), 'm-comp': 16.30}
    go('frame=opening&theme=light&t=10.0')
    mismatch = []
    for i in range(int((16.9 - 10.1) / 0.1) + 1):
        tt = 10.1 + i * 0.1
        page.evaluate(f'window.__seek({tt})')
        ids = set(probe()['graph']['ids'])
        for node, when in node_times.items():
            if (node in ids) != (tt >= when - 1 / 60):
                mismatch.append((round(tt, 1), node))
    style_ok = True
    for tc in (8.87, 12.92, 16.66):
        go(f'frame=opening&theme=light&t={tc - 0.02:.3f}')
        before = page.evaluate("""() => [...document.querySelectorAll('#graph path')]
            .filter(p => { const d = p.getAttribute('stroke-dasharray'); return d && d !== 'none'; })
            .map(p => p.getAttribute('d'))""")
        go(f'frame=opening&theme=light&t={tc + 0.02:.3f}')
        after = page.evaluate("""() => [...document.querySelectorAll('#graph path')]
            .filter(p => p.getAttribute('stroke') === 'var(--lit)')
            .map(p => [p.getAttribute('d'), p.getAttribute('stroke'), p.getAttribute('stroke-width')])""")
        for dpath in before:
            if not any(dpath == a[0] and a[1] == 'var(--lit)' and a[2] == '1.5' for a in after):
                style_ok = False
    ok23 = ok23 and not mismatch and style_ok
    check('23 graph', ok23, f"{g['nodes']} nodes, {g['counter']}, {edges} edges, {len(mismatch)} timing, style {style_ok}",
          '13 nodes, 10 drawn edges, times within a frame, finished edges keep their look')

    # ---- 24 flash ----
    flashes = [(grp[2], grp[0], grp[1] + 0.55) for grp in STAGE]
    flashes += [('m-turb', [i for ids, _, _ in STAGE for i in ids], 12.60),
                ('m-shaft', ['shaft.main'], 13.70)]
    flashes += [('c-comp4', ['compressor.stage-4'], compStart(0) + 0.40),
                ('c-comp1', ['compressor.stage-1'], compStart(5) + 0.40)]
    flashes += [('m-comp', COMP, 16.30)]
    weak = []; lines_report = []
    for name, ids, T in flashes:
        solo = ",".join(ids)
        mp = go(f'frame=opening&theme=light&mask=part:{solo}&t={T + 0.2:.3f}', which=extra[0])
        mp.screenshot(path=f'{TMP}/fm-{name}.png')
        pm = pixels(f'{TMP}/fm-{name}.png')
        go(f'frame=opening&theme=light&t={T + 0.2:.3f}', which=page)
        page.screenshot(path=f'{TMP}/fl-on.png')
        go(f'frame=opening&theme=light&t={T + 0.2:.3f}&noflash=1', which=extra[1])
        extra[1].screenshot(path=f'{TMP}/fl-off.png')
        a = pixels(f'{TMP}/fl-on.png'); bs = pixels(f'{TMP}/fl-off.png')
        pts = [(x, y) for y in range(0, 1080, 2) for x in range(0, 1280, 2) if pm[x, y][0] < 60 and far(a, x, y)]
        if not pts:
            weak.append(f'{name} no metal')
            continue
        b1 = sum(a[x, y][2] - a[x, y][0] for (x, y) in pts) / len(pts)
        b0 = sum(bs[x, y][2] - bs[x, y][0] for (x, y) in pts) / len(pts)
        pulses = probe()['graph'].get('pulse', [])
        pulse = name in pulses
        lines_report.append([name, round(T, 2), round(b1 - b0, 1), pulse])
        if b1 - b0 < 10 or not pulse:
            weak.append(f'{name} d={b1-b0:+.0f} pulse={pulse}')
    quiet = [4.0, 7.9, 11.6, 13.3, 15.2]
    quiet_worst = 0.0
    for tt in quiet:
        go(f'frame=opening&theme=light&t={tt}', which=page)
        page.screenshot(path=f'{TMP}/q-on.png')
        go(f'frame=opening&theme=light&t={tt}&noflash=1', which=extra[1])
        extra[1].screenshot(path=f'{TMP}/q-off.png')
        quiet_worst = max(quiet_worst, share(f'{TMP}/q-on.png', f'{TMP}/q-off.png', (0, 0, 1280, 1080)))
    ok24 = not weak and quiet_worst < 0.0001
    with open(f'{OUT}/m2-flash.json', 'w') as f:
        json.dump(lines_report, f)
    check('24 flash', ok24, '; '.join(weak[:3]) if weak else f'quiet frames {quiet_worst*100:.4f}%',
          'every node >= +10 blue-red with a pulse, quiet frames unchanged')

    # ---- 25 second thread fades out ----
    go('frame=opening&theme=light&t=9.85')
    op = page.evaluate("() => parseFloat(document.querySelectorAll('#thread path')[1].style.opacity || '1')")
    def thread_pixels(path):
        pp = pixels(path)
        return sum(1 for y in range(1080) for x in range(1284, 1300) if pp[x, y][2] - pp[x, y][0] > 60 and pp[x, y][2] > 120)
    go('frame=opening&theme=light&t=10.1'); page.screenshot(path=f'{TMP}/th101.png')
    go('frame=opening&theme=light&t=17.0'); page.screenshot(path=f'{TMP}/th170.png')
    after = max(thread_pixels(f'{TMP}/th101.png'), thread_pixels(f'{TMP}/th170.png'))
    ok25 = 0.30 <= op <= 0.55 and after == 0
    check('25 thread fades', ok25, f'opacity at 9.85 {op:.2f}, line pixels after 10.1 {after}',
          '0.30-0.55 at 9.85, none at 10.1 and 17.0')

    check('14b console during milestone two', not console, console[:2] or 'none', 'no error / pageerror')
    browser.close()

path = f'{OUT}/results.json'
existing = json.load(open(path)) if os.path.exists(path) else []
existing = [r for r in existing if not any(r['check'].startswith(str(n) + ' ') for n in range(18, 26))]
existing += results
with open(path, 'w') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} milestone-two checks passed')
sys.exit(0 if passed == len(results) else 1)
