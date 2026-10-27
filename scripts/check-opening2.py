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

    # ---- 20 outline first, measured in the solo picture ----
    cats = [(f'stage{i + 2}', ids, start, 0.55, 0.10, 0.20) for i, (ids, start, _) in enumerate(STAGE)]
    cats += [('shaft', ['shaft.main'], 12.70, 1.00, 0.10, 0.25),
             ('comp4', ['compressor.stage-4'], compStart(0), 0.40, 0.08, 0.14),
             ('stators', ['compressor.stators'], compStart(1), 0.40, 0.08, 0.14),
             ('comp1', ['compressor.stage-1'], compStart(5), 0.40, 0.08, 0.14),
             ('drum', ['compressor.drum'], compStart(6), 0.40, 0.08, 0.14)]
    curves = {}
    problems = []
    outline_report = []
    for name, ids, start, sweep_to, o0, o1 in cats:
        solo = ",".join(ids)
        mask_pg = go(f'frame=opening&theme=light&mask=part:{solo}&t={start:.3f}', which=extra[0])
        solo_pg = go(f'frame=opening&theme=light&solo={solo}&t={start:.3f}', which=page)
        nl_pg = go(f'frame=opening&theme=light&solo={solo}&nolines=1&noflash=1&t={start:.3f}', which=extra[1])
        times = [start - 0.05 + k / 60 for k in range(int((sweep_to + 0.10) * 60) + 1)]
        gs, os_ = [], []
        for tt in times:
            for pg in (mask_pg, solo_pg, nl_pg):
                pg.evaluate(f'window.__seek({tt:.4f})')
            mask_pg.screenshot(path=f'{TMP}/mp.png')
            solo_pg.screenshot(path=f'{TMP}/sp.png')
            nl_pg.screenshot(path=f'{TMP}/np.png')
            pm = pixels(f'{TMP}/mp.png'); ps = pixels(f'{TMP}/sp.png'); pn = pixels(f'{TMP}/np.png')
            pts = [(x, y) for y in range(0, 1080, 2) for x in range(0, 1280, 2) if pm[x, y][0] < 60]
            if not pts:
                continue
            g = sum(1 for p in pts if far(pn, p[0], p[1])) / len(pts)
            o = sum(1 for p in pts if max(abs(ps[p[0], p[1]][i] - pn[p[0], p[1]][i]) for i in range(3)) > 20) / len(pts)
            gs.append(g); os_.append(o)
            curves.setdefault(name, []).append([round(tt, 3), round(g, 4), round(o, 4)])
        idx0 = int((o0 + 0.05) * 60); idx1 = int((o1 + 0.05) * 60)
        win_g = gs[idx0:idx1 + 1]; win_o = os_[idx0:idx1 + 1]
        outline_report.append((name, round(min(win_o), 3) if win_o else 0, round(max(win_g), 3) if win_g else 0))
        if not win_o or min(win_o) < 0.01:
            problems.append(f'{name} outline {min(win_o)*100 if win_o else 0:.1f}%')
        if not win_g or max(win_g) >= 0.05:
            problems.append(f'{name} metal early {max(win_g)*100 if win_g else 0:.1f}%')
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
          'outline window O >= 1% and G < 5%, G non-decreasing, ends > 60%')

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
            .map(p => { const L = p.getTotalLength(); const a = p.getPointAtLength(0); const b = p.getPointAtLength(L);
                        return [L, a.x, a.y, b.x, b.y]; })""")
        go(f'frame=opening&theme=light&t={tc + 0.02:.3f}')
        after = page.evaluate("""() => [...document.querySelectorAll('#graph path')]
            .filter(p => p.getAttribute('stroke') === 'var(--lit)')
            .map(p => { const L = p.getTotalLength(); const a = p.getPointAtLength(0); const b = p.getPointAtLength(L);
                        return [L, a.x, a.y, b.x, b.y, p.getAttribute('stroke'), p.getAttribute('stroke-width')]; })""")
        for L, x0, y0, x1, y1 in before:
            match = False
            for q in after:
                if abs(q[0] - L) <= 0.5 and q[5] == 'var(--lit)' and q[6] == '1.5':
                    ends = abs(q[1] - x0) <= 0.5 and abs(q[2] - y0) <= 0.5 and abs(q[3] - x1) <= 0.5 and abs(q[4] - y1) <= 0.5
                    r_ends = abs(q[1] - x1) <= 0.5 and abs(q[2] - y1) <= 0.5 and abs(q[3] - x0) <= 0.5 and abs(q[4] - y0) <= 0.5
                    if ends or r_ends:
                        match = True
                        break
            if not match:
                style_ok = False
    ok23 = ok23 and not mismatch and style_ok
    check('23 graph', ok23, f"{g['nodes']} nodes, {g['counter']}, {edges} edges, {len(mismatch)} timing, style {style_ok}",
          '13 nodes, 10 drawn edges, times within a frame, finished edges keep their look')

    # ---- 24 flash, measured in the solo picture ----
    flashes = [(grp[2], grp[0], grp[1] + 0.55) for grp in STAGE]
    flashes += [('m-turb', [i for ids, _, _ in STAGE for i in ids], 12.60),
                ('m-shaft', ['shaft.main'], 13.70)]
    flashes += [('c-comp4', ['compressor.stage-4'], compStart(0) + 0.40),
                ('c-comp1', ['compressor.stage-1'], compStart(5) + 0.40)]
    flashes += [('m-comp', COMP, 16.30)]
    weak = []; lines_report = []
    for name, ids, T in flashes:
        solo = ",".join(ids)
        mask_pg = go(f'frame=opening&theme=light&mask=part:{solo}&t={T + 0.2:.3f}', which=extra[0])
        mask_pg.screenshot(path=f'{TMP}/fm.png')
        pm = pixels(f'{TMP}/fm.png')
        pts = [(x, y) for y in range(0, 1080, 2) for x in range(0, 1280, 2) if pm[x, y][0] < 60]
        on_pg = go(f'frame=opening&theme=light&solo={solo}&t={T + 0.2:.3f}', which=page)
        on_pg.screenshot(path=f'{TMP}/f-on.png')
        off_pg = go(f'frame=opening&theme=light&solo={solo}&noflash=1&t={T + 0.2:.3f}', which=extra[1])
        off_pg.screenshot(path=f'{TMP}/f-off.png')
        a = pixels(f'{TMP}/f-on.png'); bs = pixels(f'{TMP}/f-off.png')
        dpts = [(x, y) for y in range(100, 1080, 2) for x in range(0, 1280, 2)
                if max(abs(bs[x, y][i] - BG[i]) for i in range(3)) > 12]
        b1 = sum(a[x, y][2] - a[x, y][0] for (x, y) in dpts) / max(1, len(dpts))
        b0 = sum(bs[x, y][2] - bs[x, y][0] for (x, y) in dpts) / max(1, len(dpts))
        # first frame must not jump
        on_pg.evaluate(f'window.__seek({T + 1/60:.4f})'); on_pg.screenshot(path=f'{TMP}/f1.png')
        off_pg.evaluate(f'window.__seek({T + 1/60:.4f})'); off_pg.screenshot(path=f'{TMP}/f1o.png')
        p1 = pixels(f'{TMP}/f1.png'); p1o = pixels(f'{TMP}/f1o.png')
        jump = sum(1 for (x, y) in pts if max(abs(p1[x, y][i] - p1o[x, y][i]) for i in range(3)) > 12) / max(1, len(pts))
        # Smoothness of the flash itself: D = solo on - solo noflash, per channel.
        ds = []
        for k in range(27):
            tt = T - 1 / 60 + k / 60
            for pg in (on_pg, off_pg):
                pg.evaluate(f'window.__seek({tt:.4f})')
            on_pg.screenshot(path=f'{TMP}/d-on.png')
            off_pg.screenshot(path=f'{TMP}/d-off.png')
            pa_ = pixels(f'{TMP}/d-on.png'); pb_ = pixels(f'{TMP}/d-off.png')
            if not dpts:
                break
            ds.append([sum(pa_[x, y][i] - pb_[x, y][i] for (x, y) in dpts) / len(dpts) for i in range(3)])
        worst_step = 0.0
        peaks_ok = True
        for ch in range(3):
            col = [d[ch] for d in ds]
            if not col:
                continue
            step_max = max(abs(col[i + 1] - col[i]) for i in range(len(col) - 1))
            allowed = 0.15 * max(abs(v) for v in col) + 0.5
            worst_step = max(worst_step, step_max / allowed)
            if name == 'm-turb':
                continue
            sm3 = [(col[max(0, i - 1)] + col[i] + col[min(len(col) - 1, i + 1)]) / 3 for i in range(len(col))]
            peak = max(range(len(sm3)), key=lambda i: abs(sm3[i]))
            sgn = 1 if sm3[peak] >= 0 else -1
            rising = all(sgn * sm3[i + 1] >= sgn * sm3[i] - 0.5 for i in range(peak))
            falling = all(sgn * sm3[i + 1] <= sgn * sm3[i] + 0.5 for i in range(peak, len(sm3) - 1))
            if not (rising and falling):
                peaks_ok = False
        # visible in the full frame
        full_on = go(f'frame=opening&theme=light&t={T + 0.2:.3f}', which=page)
        page.screenshot(path=f'{TMP}/full-on.png')
        go(f'frame=opening&theme=light&t={T + 0.2:.3f}&noflash=1', which=extra[1])
        extra[1].screenshot(path=f'{TMP}/full-off.png')
        pf = pixels(f'{TMP}/full-on.png'); pfo = pixels(f'{TMP}/full-off.png')
        visible = sum(1 for y in range(1080) for x in range(1280)
                      if max(abs(pf[x, y][i] - pfo[x, y][i]) for i in range(3)) > 8)
        pulse = name in probe()['graph'].get('pulse', [])
        lines_report.append([name, round(T, 2), round(b1 - b0, 1), round(jump * 100, 2), round(worst_step, 2), visible, pulse])
        if b1 - b0 < 10 or (jump >= 0.005 and name != 'm-turb') or worst_step > 1.0 or not peaks_ok or visible < 1000 or not pulse:
            weak.append(f'{name} d={b1-b0:+.0f} jump={jump*100:.2f}% step={worst_step*100:.0f}% onePeak={peaks_ok} vis={visible} pulse={pulse}')
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
          'each node: +10 blue-red, first frame < 0.5%, D step <= 0.15 x peak + 0.5, one peak, >= 1000 px, pulse')

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

    # ---- 26 the part mask really is that part ----
    m2_ids = ",".join(STAGE[0][0]); m3_ids = ",".join(STAGE[1][0])
    go(f'frame=opening&theme=light&mask=part:{m2_ids}&t=10.85', which=extra[0])
    extra[0].screenshot(path=f'{TMP}/k2.png')
    go(f'frame=opening&theme=light&mask=part:{m3_ids}&t=10.85', which=extra[1])
    extra[1].screenshot(path=f'{TMP}/k3.png')
    p2 = pixels(f'{TMP}/k2.png'); p3 = pixels(f'{TMP}/k3.png')
    distinct = sum(1 for y in range(0, 1080, 2) for x in range(0, 1280, 2) if (p2[x, y][0] < 60) != (p3[x, y][0] < 60))
    ious = []
    for name, ids, start, sweep_to, o0, o1 in cats:
        solo = ",".join(ids)
        when = start + sweep_to + 0.2
        go(f'frame=opening&theme=light&mask=part:{solo}&t={when:.3f}', which=extra[0])
        extra[0].screenshot(path=f'{TMP}/i-mask.png')
        go(f'frame=opening&theme=light&solo={solo}&t={when:.3f}', which=page)
        page.screenshot(path=f'{TMP}/i-solo.png')
        pm = pixels(f'{TMP}/i-mask.png'); psl = pixels(f'{TMP}/i-solo.png')
        inter = uni = 0
        for y in range(100, 1080, 2):
            for x in range(0, 1280, 2):
                m = max(pm[x, y]) < 245
                q = max(abs(psl[x, y][i] - BG[i]) for i in range(3)) > 12
                if m and q: inter += 1
                if m or q: uni += 1
        ious.append(round(inter / max(1, uni), 3))
    ok26 = distinct > 0 and min(ious) >= 0.85
    check('26 part mask', ok26, f's2 vs s3 differ at {distinct} px, IoU min {min(ious):.3f}',
          'the two masks differ, and each mask matches its solo part (IoU >= 0.85)')

    # ---- 27 instanced parts do show their outline ----
    checks27 = [
        ('stage2-blades', 'turbine.stage-2-blades', STAGE[0][0], 10.10, 0.15),
        ('stage2-outer', 'turbine.stage-2-outer', STAGE[0][0], 10.10, 0.15),
        ('comp4-blades', 'compressor.stage-4', ['compressor.stage-4'], compStart(0), 0.11),
        ('stators', 'compressor.stators', ['compressor.stators'], compStart(1), 0.11),
        ('comp1', 'compressor.stage-1', ['compressor.stage-1'], compStart(5), 0.11),
    ]
    rows27 = []; bad27 = []
    for name, part, solo_ids, start, off in checks27:
        solo = ",".join(solo_ids)
        tt = start + off
        mp = go(f'frame=opening&theme=light&mask=part:{part}&t={tt:.3f}', which=extra[0])
        mp.screenshot(path=f'{TMP}/p27-mask.png')
        on = go(f'frame=opening&theme=light&solo={solo}&t={tt:.3f}', which=page)
        on.screenshot(path=f'{TMP}/p27-on.png')
        off_pg = go(f'frame=opening&theme=light&solo={solo}&nolines=1&t={tt:.3f}', which=extra[1])
        off_pg.screenshot(path=f'{TMP}/p27-off.png')
        pm = pixels(f'{TMP}/p27-mask.png'); pa = pixels(f'{TMP}/p27-on.png'); pb = pixels(f'{TMP}/p27-off.png')
        pts = [(x, y) for y in range(100, 1080, 2) for x in range(0, 1280, 2) if max(pm[x, y]) < 245]
        if not pts:
            bad27.append(f'{name} empty mask')
            continue
        o = sum(1 for (x, y) in pts if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20) / len(pts)
        g = sum(1 for (x, y) in pts if far(pb, x, y)) / len(pts)
        rows27.append([name, round(o, 3), round(g, 3)])
        if o < 0.01 or g >= 0.05:
            bad27.append(f'{name} O={o*100:.1f}% G={g*100:.1f}%')
    check('27 instanced outlines', not bad27, '; '.join(bad27[:3]) if bad27 else str(rows27),
          'outline instant: O >= 1%, G < 5% for every instanced part')

    # ---- 28 the ring fills in outline first ----
    go('frame=opening&theme=light&t=7.4')
    bad28 = []
    for i in range(int((8.70 - 7.40) * 60) + 1):
        tt = 7.40 + i / 60
        page.evaluate(f'window.__seek({tt})')
        pr = probe()['blades']
        expect = 1 if tt >= 7.60 else 0
        for k in range(2, 101):
            if tt >= 7.65 + 0.95 * math.sqrt((k - 2) / 98) + (0.30 - 0.20 * ((k - 2) / 98)):
                expect = k
        if pr['solid'] != expect:
            bad28.append(f'{tt:.2f}s solid {pr["solid"]} != {expect}')
            break
    for tt in (7.90, 8.20):
        go(f'frame=opening&theme=light&t={tt}', which=page)
        page.screenshot(path=f'{TMP}/r-on.png')
        go(f'frame=opening&theme=light&t={tt}&nolines=1', which=extra[1])
        extra[1].screenshot(path=f'{TMP}/r-off.png')
        pa = pixels(f'{TMP}/r-on.png'); pb = pixels(f'{TMP}/r-off.png')
        n = sum(1 for y in range(0, 1080) for x in range(0, 1280)
                if max(abs(pa[x, y][i] - pb[x, y][i]) for i in range(3)) > 20)
        if n < 1500:
            bad28.append(f'{tt}s only {n} outline px')
    check('28 ring outline first', not bad28, '; '.join(bad28[:2]) if bad28 else 'solid count follows t_k + w_k, outlines visible',
          'solid blades match the schedule, >= 1500 outline pixels at 7.90 and 8.20')

    check('14b console during milestone two', not console, console[:2] or 'none', 'no error / pageerror')
    browser.close()

path = f'{OUT}/results.json'
existing = json.load(open(path)) if os.path.exists(path) else []
existing = [r for r in existing if not any(r['check'].startswith(str(n) + ' ') for n in range(18, 29))]
existing += results
with open(path, 'w') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
passed = sum(1 for r in results if r['ok'])
print(f'\n{passed}/{len(results)} milestone-two checks passed')
sys.exit(0 if passed == len(results) else 1)
