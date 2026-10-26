"""Checks 18-24 for opening milestone two; appends to review/opening/results.json."""
import json, math, os, sys, time
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = '<项目目录>'
OUT = f'{ROOT}/review/opening'
URL = 'http://127.0.0.1:5192/frames.html'
BASE_URL = 'http://127.0.0.1:5193/frames.html'
BG = (0xee, 0xf0, 0xee)
TMP = '/tmp/opening-check2'
os.makedirs(TMP, exist_ok=True)

results = []
def check(name, ok, value, expect):
    results.append({'check': name, 'ok': bool(ok), 'value': value, 'expect': expect})
    print(('PASS' if ok else 'FAIL'), name, '|', value, '|', expect, flush=True)

def load_rgb(path):
    im = Image.open(path).convert('RGB')
    return im, im.load()

OUTLINE = (78, 94, 107)

def far_from_bg(px, x, y, tol=40):
    r, g, b = px[x, y]
    far = max(abs(r - BG[0]), abs(g - BG[1]), abs(b - BG[2])) > tol
    # Outline pixels are dark grey and sit far from the background too; a part
    # only counts as metal once it stops looking like its own contour.
    line = max(abs(r - OUTLINE[0]), abs(g - OUTLINE[1]), abs(b - OUTLINE[2])) < 25
    return far and not line

def share_diff(a, b, tol=8):
    ia, pa = load_rgb(a); ib, pb = load_rgb(b)
    w, h = ia.size
    bad = 0
    for y in range(0, h):
        for x in range(0, w):
            ca, cb = pa[x, y], pb[x, y]
            if max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1]), abs(ca[2] - cb[2])) > tol:
                bad += 1
    return bad / (w * h)

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
    mask_page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)

    def go(query, base=False):
        page.goto((BASE_URL if base else URL) + '?' + query)
        page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
        time.sleep(0.4)

    def probe():
        return page.evaluate('window.__openingProbe()')

    # ---- 18 continuity with milestone one ----
    go('frame=opening&theme=light&t=9.6')
    a = f'{TMP}/join-now.png'; page.screenshot(path=a)
    ref_probe = probe()
    go('frame=opening&theme=light&t=9.6', base=True)
    b = f'{TMP}/join-base.png'; page.screenshot(path=b)
    base_probe = probe()
    s18 = share_diff(a, b)
    cam_same = max(abs(x - y) for x, y in zip(ref_probe['camera']['position'], base_probe['camera']['position'])) < 1e-6
    check('18 join at 9.6', s18 < 0.0001 and cam_same, f'{s18*100:.4f}%, camera same {cam_same}', '< 0.01% and identical camera')

    # ---- 19 parts arrive on schedule ----
    schedule = {}
    for ids, start, _ in STAGE:
        for cid in ids:
            schedule[cid] = start
    schedule['shaft.main'] = 12.70
    for i, cid in enumerate(COMP):
        schedule[cid] = compStart(i)
    late = []
    go('frame=opening&theme=light&t=9.6')
    firsts = {}
    for i in range(int((17.0 - 9.6) * 60) + 1):
        tt = 9.6 + i / 60
        page.evaluate(f'window.__seek({tt})')
        comps = probe()['components']
        for cid, start in schedule.items():
            if cid not in firsts and comps.get(cid):
                firsts[cid] = tt
    for cid, start in schedule.items():
        got = firsts.get(cid)
        if got is None or abs(got - start) > 1 / 60 + 1e-6:
            late.append((cid, got, start))
    go('frame=opening&theme=light&t=17.0')
    parts = probe()['visibleParts']
    check('19 parts arrive', not late and parts == 1406,
          f'{len(late)} mismatches, visible parts {parts}', 'schedule within a frame, 1406 parts')

    # ---- 20 outline before metal, in the real picture ----
    cats = [(f'stage{i + 2}', ids, start, 0.6) for i, (ids, start, _) in enumerate(STAGE)]
    cats.append(('shaft', ['shaft.main'], 12.70, 1.0))
    cats.append(('comp4', ['compressor.stage-4'], compStart(0), 0.4))
    cats.append(('comp1', ['compressor.stage-1'], compStart(5), 0.4))
    cats.append(('drum', ['compressor.drum'], compStart(6), 0.4))
    curves = {}
    problems = []
    for name, ids, start, dur in cats:
        solo = ",".join(ids)
        end_t = start + dur + 0.15
        frames = int(round((end_t - (start - 0.1)) * 60))
        times = [start - 0.1 + k / 60 for k in range(frames + 1)]
        go(f'frame=opening&theme=light&solo={solo}&t={times[0]:.4f}')
        shots = []
        for tt in times:
            page.evaluate(f'window.__seek({tt:.4f})')
            path = f'{TMP}/solo-{name}-{len(shots):03d}.png'
            page.screenshot(path=path)
            shots.append(path)
        final_px = load_rgb(shots[-1])[1]
        # The finished part tells us which pixels belong to it and what they
        # should look like; anything still short of that is unrevealed.
        sil = [(x, y) for y in range(0, 1080, 2) for x in range(0, 1280, 2)
               if max(abs(final_px[x, y][0] - BG[0]), abs(final_px[x, y][1] - BG[1]), abs(final_px[x, y][2] - BG[2])) > 40]
        F = len(sil)
        series = []
        for tt, path in zip(times, shots):
            cur = load_rgb(path)[1]
            hits = 0
            for (x, y) in sil:
                r, g, b = cur[x, y]
                fr, fg, fb = final_px[x, y]
                if max(abs(r - fr), abs(g - fg), abs(b - fb)) <= 45:
                    hits += 1
            series.append((round(tt, 3), hits / max(1, F)))
        curves[name] = series
        if F < 500:
            problems.append(f'{name} mask only {F}px')
            continue
        first = next((i for i, (tt, g) in enumerate(series) if tt >= start - 1 / 60), 0)
        if series[first][1] >= 0.15:
            problems.append(f'{name} starts at {series[first][1]*100:.0f}% metal')
        for i in range(first + 1, len(series)):
            if series[i][1] < series[i - 1][1] - 0.02:
                problems.append(f'{name} drops at {series[i][0]:.2f}s')
                break
        if series[-1][1] <= 0.6:
            problems.append(f'{name} ends at {series[-1][1]*100:.0f}%')
    with open(f'{OUT}/m2-curves.json', 'w') as f:
        json.dump(curves, f)
    check('20 outline before metal', not problems, '; '.join(problems[:3]) if problems else 'all start as outline, rise, finish above 60%',
          'first frame < 15% metal, non-decreasing, > 60% when done')

    # ---- 21 nothing leaves the frame ----
    worst = (999, 0)
    go('frame=opening&theme=light&mask=1&t=9.6')
    for i in range(int((17.0 - 9.6) / 0.1) + 1):
        tt = 9.6 + i * 0.1
        page.evaluate(f'window.__seek({tt})')
        time.sleep(0.02)
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
    n = math.sqrt(sum(v * v for v in d))
    d = [v / n for v in d]
    target = [0.62, 0.27, 0.73]
    tn = math.sqrt(sum(v * v for v in target))
    target = [v / tn for v in target]
    angle = math.degrees(math.acos(max(-1, min(1, sum(a * b for a, b in zip(d, target))))))
    go('frame=opening&theme=light&t=9.6')
    positions = []
    for i in range(int((17.0 - 9.6) * 60) + 1):
        tt = 9.6 + i / 60
        page.evaluate(f'window.__seek({tt})')
        positions.append(probe()['camera']['position'])
    steps = [math.dist(positions[i], positions[i + 1]) for i in range(len(positions) - 1)]
    jerks = [abs(steps[i + 1] - steps[i]) for i in range(len(steps) - 1)]
    med = sorted(steps)[len(steps) // 2]
    medj = sorted(jerks)[len(jerks) // 2]
    ok22 = angle <= 1 and max(steps) <= 4 * max(med, 1e-9) and max(jerks) <= 4 * max(medj, 1e-9)
    check('22 camera', ok22, f'end angle {angle:.2f}deg, step max {max(steps):.4f} (median {med:.4f}), jerk max {max(jerks):.4f} (median {medj:.4f})',
          'angle <= 1deg, steps and jerks <= 4x median')

    # ---- 23 graph ----
    go('frame=opening&theme=light&t=17.0')
    g = probe()['graph']
    texts = ' '.join(g['texts'])
    ok23 = (g['nodes'] == 13 and g['counter'] == '13 个节点 · 10 条关系'
            and not any(k in texts for k in ('转子', '7 号发动机', '研发', '生产', '质量', '供应链')))
    node_times = {'c-t2': 10.10, 'c-t3': 10.70, 'c-t4': 11.30, 'c-t5': 11.90, 'm-turb': 12.60,
                  'm-shaft': 12.70, 'c-comp4': compStart(0), 'c-comp3': compStart(2),
                  'c-comp2': compStart(4), 'c-comp1': compStart(5), 'm-comp': 16.30}
    go('frame=opening&theme=light&t=10.0')
    seen = set()
    mismatch = []
    for i in range(int((16.9 - 10.1) / 0.1) + 1):
        tt = 10.1 + i * 0.1
        page.evaluate(f'window.__seek({tt})')
        ids = set(probe()['graph']['ids'])
        for node, when in node_times.items():
            if (node in ids) != (tt >= when - 1 / 60):
                mismatch.append((round(tt, 1), node))
    ok23 = ok23 and not mismatch
    check('23 graph', ok23, f"{g['nodes']} nodes, {g['counter']}, {len(mismatch)} timing mismatches",
          '13 nodes, 10 edges, no extra nodes, times within a frame')

    # ---- 24 flash on each new node ----
    flash_nodes = [
        ('c-t2', STAGE[0][0], STAGE[0][1]), ('c-t3', STAGE[1][0], STAGE[1][1]),
        ('c-t4', STAGE[2][0], STAGE[2][1]), ('c-t5', STAGE[3][0], STAGE[3][1]),
        ('m-turb', [i for ids, _, _ in STAGE for i in ids], 12.60),
        ('m-shaft', ['shaft.main'], 12.70),
        ('c-comp4', ['compressor.stage-4'], compStart(0)),
        ('c-comp1', ['compressor.stage-1'], compStart(5)),
        ('m-comp', COMP, 16.30),
    ]
    weak = []
    for name, ids, when in flash_nodes:
        go(f'frame=opening&theme=light&mask=part:{",".join(ids)}&t={when + 0.3:.2f}')
        page.screenshot(path=f'{TMP}/fm-{name}.png')
        _, pm = load_rgb(f'{TMP}/fm-{name}.png')
        def grab(tt):
            go(f'frame=opening&theme=light&t={tt:.2f}')
            page.screenshot(path=f'{TMP}/fr-{name}.png')
            return load_rgb(f'{TMP}/fr-{name}.png')[1]
        before = grab(when - 0.1)
        after = grab(when + 0.2)
        # Only pixels that already show metal after the flash: unrevealed area
        # is background in both frames and would just dilute the measurement.
        pts = [(x, y) for y in range(0, 1080, 2) for x in range(0, 1280, 2)
               if pm[x, y][0] < 60 and far_from_bg(after, x, y)]
        if not pts:
            weak.append(f'{name} no metal')
            continue
        b0 = sum(before[x, y][2] - before[x, y][0] for (x, y) in pts) / len(pts)
        b1 = sum(after[x, y][2] - after[x, y][0] for (x, y) in pts) / len(pts)
        if b1 - b0 < 10:
            weak.append(f'{name} {b1 - b0:+.0f}')
    check('24 flash', not weak, '; '.join(weak) if weak else 'every node flashes at least +10 blue-red',
          'blue-red rises by >= 10 after each node appears')

    check('14b console during milestone two', not console, console[:2] or 'none', 'no error / pageerror')
    browser.close()

path = f'{OUT}/results.json'
existing = json.load(open(path)) if os.path.exists(path) else []
existing = [r for r in existing if not any(r['check'].startswith(str(n) + ' ') for n in range(18, 25))]
existing += results
with open(path, 'w') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} milestone-two checks passed')
sys.exit(0 if passed == len(results) else 1)
