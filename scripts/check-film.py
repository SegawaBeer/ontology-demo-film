"""Checks for the whole main timeline, 30–120 s (任务说明/主时间轴二任务说明.md, 第五节).

Part 1 runs check-film-a.py on frame=film (F1–F15 over 30–64, keys F1..F15).
Part 2 (this file) checks 64–120: keys 'F2+' etc. extend F1..F15 to 30–120, and G1–G6.
frame=film covers 30–103; frame=ending covers 103–120 (both carry the same __events).

Usage: check-film.py [--skip-a] [--only G1,F9+] [--out review/film]
Needs 5194 (this branch), 5195 (1dc6a6c) and 5193 (89aca04).
"""
import io, json, math, os, re, subprocess, sys, time
from PIL import Image, ImageChops, ImageDraw
from playwright.sync_api import sync_playwright

NEW = 'http://127.0.0.1:5194/frames.html'
OPEN_BASE = 'http://127.0.0.1:5193/frames.html'   # 89aca04, opening accepted
HERE = os.path.dirname(os.path.abspath(__file__))
SRC_A = open(os.path.join(HERE, 'check-film-a.py')).read()
js_of = lambda name: re.search(name + r' = r?"""(.*?)"""', SRC_A, re.S).group(1)
LAYOUT_JS, CAM_INIT = js_of('LAYOUT_JS'), js_of('CAM_INIT')
F15_JS = open(os.path.join(HERE, 'f15-lines.js')).read()
FOLD_JS = open(os.path.join(HERE, 'fold-check.js')).read()
G3_JS = open(os.path.join(HERE, 'g3-seat.js')).read()
FILM = f'{NEW}?frame=film&theme=light'
END = f'{NEW}?frame=ending&theme=light'
FPS = 60
HANDOFF = 103.0
args = sys.argv[1:]
ONLY = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
OUT = args[args.index('--out') + 1] if '--out' in args else os.path.join(HERE, '..', 'review', 'film')
os.makedirs(OUT, exist_ok=True)
RESULTS_PATH = os.path.join(OUT, 'results.json')

if '--skip-a' not in args and ONLY is None:
    subprocess.run([sys.executable, os.path.join(HERE, 'check-film-a.py'), '--frame', 'film', '--out', OUT], check=False)
results = json.load(open(RESULTS_PATH)) if os.path.exists(RESULTS_PATH) else {}
console = []


def record(key, ok, **detail):
    results[key] = {'pass': bool(ok), **detail}
    json.dump(results, open(RESULTS_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f'{key}: {"PASS" if ok else "FAIL"}', json.dumps(detail, ensure_ascii=False)[:600], flush=True)


def want(key):
    return ONLY is None or key in ONLY


def new_page(browser, label):
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.add_init_script(CAM_INIT)
    page.on('console', lambda m: console.append({'page': label, 'type': m.type, 'text': m.text[:300]}) if m.type in ('error', 'warning') else None)
    page.on('pageerror', lambda e: console.append({'page': label, 'type': 'pageerror', 'text': str(e)[:300]}))
    return page


def load(page, url):
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=180000)
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(250)


def shot(page, clip=None):
    kw = {'clip': {'x': clip[0], 'y': clip[1], 'width': clip[2] - clip[0], 'height': clip[3] - clip[1]}} if clip else {}
    return Image.open(io.BytesIO(page.screenshot(**kw))).convert('RGB')


def diffmax(a, b):
    r, g, bl = ImageChops.difference(a, b).split()
    return ImageChops.lighter(ImageChops.lighter(r, g), bl)


def over(m, thr=8):
    return sum(m.histogram()[thr + 1:])


def mean_diff(a, b):
    hs = [c.histogram() for c in ImageChops.difference(a, b).split()]
    return sum(i * v for h in hs for i, v in enumerate(h)) / (a.size[0] * a.size[1] * 3)


def seek(page, t):
    page.evaluate(f'window.__seek({t})')


def probe(page):
    return page.evaluate('window.__filmProbe()')


def page_for(t):
    """frame=film up to the hand-off, frame=ending from it."""
    return FILM if t < HANDOFF else END


def cam_of(page):
    return page.evaluate("""() => { const c = window.__lastCam; c.updateMatrixWorld();
      const d = new c.position.constructor(0, 0, -1).applyQuaternion(c.quaternion);
      return { p: c.position.toArray(), d: d.toArray() }; }""")


def cam_diff(ca, cb):
    dot = sum(x * y for x, y in zip(ca['d'], cb['d']))
    return math.dist(ca['p'], cb['p']), math.degrees(math.acos(max(-1, min(1, dot))))


def frames_of(a, b):
    return [f / FPS for f in range(int(round(a * FPS)), int(round(b * FPS)) + 1)]
# ---- CHECKS BELOW ----


# ---------------------------------------------------------------- G1
def g1(browser):
    pa, pb = new_page(browser, 'g1-film'), new_page(browser, 'g1-clip')
    load(pa, FILM + '&play=0')
    rows, ok = [], True
    for i in range(45):
        t = 64 + i * 0.5
        seek(pa, t); pa.wait_for_timeout(100)
        load(pb, f'{NEW}?frame=clip&theme=light&t={t - 64}')
        m = diffmax(shot(pa), shot(pb)); n = over(m)
        pct = 100 * n / (1920 * 1080)
        ok &= pct < 0.01
        if n: rows.append({'t': t, 'over8': n, 'pct': round(pct, 5), 'bbox': m.point(lambda v: 255 if v > 8 else 0).getbbox()})
    pa.close(); pb.close()
    record('G1', ok, samples=45, differing=rows, note='film at t vs frame=clip at t - 64, opened directly; channel difference > 8 under 0.01 % of the frame')


# ---------------------------------------------------------------- G2
G2_JS = r"""() => { const T = el => el ? el.innerText.replace(/\s+/g, ' ').trim() : '';
  const turns = [...document.querySelectorAll('#dialog .turns > .turn')];
  const q4 = turns.find(x => T(x.querySelector('.meta')).startsWith('供应链')), q2 = turns.find(x => T(x.querySelector('.meta')).startsWith('总装'));
  const now = q2 ? q2.querySelector('.answer .now:not(.struck)') : null, nowStyle = now ? getComputedStyle(now).color : '';
  const probeColour = v => { const e = document.createElement('span'); e.style.color = `var(${v})`; document.body.append(e); const c = getComputedStyle(e).color; e.remove(); return c; };
  return { red: probeColour('--red'), green: probeColour('--green'), ems: q4 ? [...q4.querySelectorAll('.step em')].map(e => e.innerText) : [], plans: q4 ? [...q4.querySelectorAll('.plan')].map(p => [T(p.querySelector('b')), T(p.querySelector('span'))]) : [],
    q2: now ? T(now) : '', q2colour: nowStyle, q2class: now ? now.className : '',
    tags: [...document.querySelectorAll('#callout-labels .gap-tag')].map(T), trace: [...document.querySelectorAll('#dialog .trace span')].map(T),
    stock: [...document.querySelectorAll('#graph [data-node="stock"] text')].map(t => t.textContent),
    ring: [...document.querySelectorAll('#graph [data-node="blade"] text')].map(t => t.textContent) }; }"""


def g2(browser):
    page = new_page(browser, 'g2')
    load(page, FILM + '&play=0')
    seek(page, 85.0); red = page.evaluate(G2_JS)
    seek(page, 95.0); mid = page.evaluate(G2_JS)
    seek(page, 100.0); end = page.evaluate(G2_JS)
    page.close()
    n = [int(x) for x in end['ems']]
    tag = [int(x.split(' ')[0]) for x in mid['tags']]
    stock = [int(re.search(r'(\d+) 枚', x).group(1)) for x in mid['stock'] if '枚' in x]
    sum_ok = len(n) == 2 and sum(n) == 16 and sorted(tag) == sorted(n) and sorted(stock) == sorted(n)
    red_ok = '暂不能上试车台' in red['q2'] and red['q2colour'] == red['red']
    green_ok = end['q2'] == '可以按时上试车台 · 09:00' and end['q2colour'] == end['green']
    plans_ok = end['plans'] == [['调本库 6 枚、二号厂区 10 枚', '05:10 前到齐 · 上试车台时间不变'], ['合格粉末重新喷涂 16 枚', '推迟 6 天']]
    trace_ok = end['trace'] == ['已检索 5 类对象 · 64 条关系', '0.5 秒']
    record('G2', sum_ok and red_ok and green_ok and plans_ok and trace_ok, dialog_numbers=n, gap_tags=mid['tags'], stock_chips=mid['stock'],
           q2_before=[red['q2'], red['q2colour']], q2_after=[end['q2'], end['q2colour']], plans=end['plans'], trace=end['trace'], blade_chip_end=end['ring'],
           rule='16 = 6 + 10 in the dialog, the 3D gap tags and the stock chips; question two red at 85 s, green 「可以按时上试车台 · 09:00」 at 100 s')


# ---------------------------------------------------------------- G3
G3_SEAT_JS = r"""() => { const { e7, clip, q4, THREE } = window.__filmDebug; let worst = 0, promoted = 0;
  for (const id of clip.hit7) { const s = e7.parts.get(id); if (s.promoted) promoted++;
    const m = new THREE.Matrix4(); s.group.mesh.getMatrixAt(s.index, m); const a = m.elements, b = s.matrix.elements;
    for (let i = 0; i < 16; i++) worst = Math.max(worst, Math.abs(a[i] - b[i])); }
  const ring = e7.listParts('turbine.stage-1-blades');
  const shown = ring.filter(id => { const s = e7.parts.get(id); if (!s.visible) return false; const m = new THREE.Matrix4(); s.group.mesh.getMatrixAt(s.index, m); return Math.abs(m.determinant()) > 1e-12 || s.promoted; }).length;
  let extra = 0; e7.extracted.traverse(o => { if (o.isMesh && clip.hit7.includes(o.userData.partId)) extra++; });
  return { worst, promoted, shown, extra }; }"""


def g3(browser):
    page = new_page(browser, 'g3')
    load(page, FILM + '&play=0')
    page.add_script_tag(content=G3_JS)
    seek(page, 96.0)
    setup = page.evaluate('window.__g3.setup(0.02)')
    worst, bad, frames = 0, [], 0
    for t in frames_of(96.0, 98.4):
        seek(page, t)
        r = page.evaluate(f'window.__g3.step({t})')
        frames += 1
        worst = max(worst, r['worst'])
        if r['bad'] and len(bad) < 10: bad.append([round(t, 3), r['bad'][:3]])
    seats = {}
    for t in (98.4, 100.0):
        seek(page, t); seats[t] = page.evaluate(G3_SEAT_JS)
    page.close()
    s = seats[100.0]
    ok = not bad and s['worst'] <= 0.0005 and s['promoted'] == 0 and s['extra'] == 0 and s['shown'] == 100
    record('G3', ok, section=setup, frames=frames, worst_overlap=worst, violations=bad, seated=seats,
           note='each flying blade vs every drawn ring blade and disk part, 0.02 bins, every frame 96.0-98.4; seated: instance matrix vs assembly matrix, '
                'no own meshes left for the 16, 100 ring blades drawn')


# ---------------------------------------------------------------- G4
def g4(browser):
    pa, pb = new_page(browser, 'g4-end'), new_page(browser, 'g4-ref')
    load(pa, f'{END}&t=120'); load(pb, f'{NEW}?frame=opening&theme=light&t=4')
    a, b = shot(pa), shot(pb)
    sub = pa.evaluate("(() => { const r = document.querySelector('.film-subtitle').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()")
    ca, cb = cam_of(pa), cam_of(pb)
    m = diffmax(a, b)
    ImageDraw.Draw(m).rectangle([0, sub[1] - 4, 1920, sub[3] + 4], fill=0)    # the subtitle band
    n = over(m); dp, ang = cam_diff(ca, cb)
    ok120 = 100 * n / (1920 * 1080) < 0.01
    # Hand-off: frame=film at 103.0 against frame=ending at 103.0.
    load(pa, f'{FILM}&t={HANDOFF}'); load(pb, f'{END}&t={HANDOFF}')
    c, d = shot(pa), shot(pb)
    m2 = diffmax(c, d); n2 = over(m2)
    c1, c2 = cam_of(pa), cam_of(pb); dp2, ang2 = cam_diff(c1, c2)
    okh = 100 * n2 / (1920 * 1080) < 0.01 and dp2 <= 0.002 and ang2 <= 0.01
    pa.close(); pb.close()
    record('G4', ok120 and okh, at120={'over8_outside_subtitle': n, 'pct': round(100 * n / (1920 * 1080), 5), 'subtitle_box': sub, 'cam_pos_diff': dp, 'cam_angle_deg': ang},
           handoff_103={'over8': n2, 'pct': round(100 * n2 / (1920 * 1080), 5), 'bbox': m2.point(lambda v: 255 if v > 8 else 0).getbbox(), 'cam_pos_diff': dp2, 'cam_angle_deg': ang2},
           note='the ending page takes over at 103.0 (not 109.0): from there it runs on the opening engine and rig')
    return a, b, m, c, d, m2


# ---------------------------------------------------------------- G5
G5_JS = r"""() => { const el = document.querySelector('.film-subtitle'); const s = getComputedStyle(el);
  const range = document.createRange(); range.selectNodeContents(el); const r = range.getBoundingClientRect();
  const others = [...document.querySelectorAll('#frame text, #frame .model-caption span, #callout-labels > div')].filter(x => x.getBoundingClientRect().width > 0)
    .map(x => { const q = x.getBoundingClientRect(); return [x.textContent.slice(0, 12), q.left, q.top, q.right, q.bottom]; })
    .filter(([, a, b, c, d]) => Math.min(c, r.right) - Math.max(a, r.left) > 0 && Math.min(d, r.bottom) - Math.max(b, r.top) > 0);
  return { text: el.textContent, opacity: +s.opacity, font: s.fontFamily, size: s.fontSize, box: [r.left, r.top, r.right, r.bottom], overlaps: others,
    headFont: getComputedStyle(document.querySelector('.model-caption')).fontFamily }; }"""


def g5(browser):
    page = new_page(browser, 'g5')
    load(page, f'{END}&t=120')
    r = page.evaluate(G5_JS)
    img = shot(page)
    page.close()
    # Ink of the line on the real picture: pixels darker than the background inside its band.
    x0, y0, x1, y1 = [int(v) for v in r['box']]
    band = img.crop((0, y0 - 2, 1920, y1 + 2)).convert('L')
    bgv = band.getpixel((5, 2))
    xs = [x for x in range(1920) if any(abs(band.getpixel((x, y)) - bgv) > 24 for y in range(band.size[1]))]
    left, right = (xs[0], 1919 - xs[-1]) if xs else (0, 0)
    ok = r['text'] == '同一套对象，整个工厂一起用。' and abs(left - right) <= 2 and not r['overlaps'] and r['font'] == r['headFont'] and r['opacity'] > 0.99
    record('G5', ok, text=r['text'], ink_margins=[left, right], box=r['box'], font=r['font'], size=r['size'], overlaps=r['overlaps'],
           note='margins measured on the drawn ink of the line (pixels > 24 levels from the background), not on the text box')


# ---------------------------------------------------------------- G6, F13+ (sound events, 64–120)
EVT_JS = r"""() => { const p = window.__filmProbe();
  const asks = [...document.querySelectorAll('#dialog .turn .ask')].map(a => [...a.textContent].length);
  return { asks: asks.reduce((a, b) => a + b, 0), steps: document.querySelectorAll('#dialog .turn:not(.past) .step').length,
    plans: [...document.querySelectorAll('#dialog .plan')].filter(x => getComputedStyle(x).visibility !== 'hidden').length,   // like steps: in the DOM from its start time
    draws: [...document.querySelectorAll('#graph [data-draw]')].map(x => x.getAttribute('data-draw')),
    green: (document.querySelector('#dialog .answer .now.green')?.textContent ?? '').length }; }"""


def g6(browser):
    page = new_page(browser, 'g6')
    load(page, FILM + '&play=0')
    events = page.evaluate('window.__events')
    tl = []
    for t in frames_of(64.0, 101.0):
        seek(page, t); tl.append((round(t * FPS), page.evaluate(EVT_JS)))
    load(page, END + '&play=0')
    events_end = page.evaluate('window.__events')
    page.close()
    bad = []
    near = lambda et, f, tol=1: f is not None and abs(f - et * FPS) <= tol
    # Typing: one type event per character that appears (the clip's two questions and question four).
    tf = [f for (f, s), (_, p) in zip(tl[1:], tl) if s['asks'] > p['asks'] for _ in range(s['asks'] - p['asks'])]
    te = sorted(e['t'] for e in events if e['kind'] == 'type' and e['t'] >= 64)
    if len(tf) != len(te): bad.append(['type count', len(te), len(tf)])
    for et, f in zip(te, tf):
        if not near(et, f): bad.append(['type', et, f / FPS])
    # Links: one path event where each drawing starts.
    starts = {}
    for f, s in tl:
        for d in s['draws']:
            if d not in starts or f - starts[d][-1][1] > 1: starts.setdefault(d, []).append([f, f])
            else: starts[d][-1][1] = f
    pf = sorted(r[0] for v in starts.values() for r in v)
    pe = sorted(e['t'] for e in events if e['kind'] == 'path' and 64 <= e['t'] < 101)
    if len(pf) != len(pe): bad.append(['path count', len(pe), len(pf)])
    for et, f in zip(pe, pf):
        if not near(et, f, 1.5): bad.append(['path', et, f / FPS])
    # Answer lines and plan cards.
    sf = [f for (f, s), (_, p) in zip(tl[1:], tl) if s['steps'] > p['steps'] or s['plans'] > p['plans']]
    le = sorted(e['t'] for e in events if e['kind'] == 'line' and e['src'] == 'dialog' and 64 <= e['t'] < 101)
    missing = [f / FPS for f in sf if not any(near(et, f) for et in le)]
    if missing: bad.append(['line missing at', missing[:6]])
    green = next((f for f, s in tl if s['green'] > 0), None)
    if not any(abs(et - 98.6) < 1e-6 for et in le) or green is None or green / FPS - 98.6 > 0.75: bad.append(['green answer', green and green / FPS])
    kinds = sorted({e['kind'] for e in events})
    allowed = {'type', 'line', 'tick', 'path', 'slide', 'part', 'swap', 'alert', 'tone'}
    fields_ok = all(e.get('src') in ('dialog', 'graph', '3d') and (e['kind'] != 'slide' or 'dur' in e) for e in events)
    span = [min(e['t'] for e in events), max(e['t'] for e in events)]
    count = lambda k, a, b: sum(1 for e in events if e['kind'] == k and a <= e['t'] < b)
    need = {'clip typing': count('type', 64, 86) == len('这批粉末都用到哪儿了？') + len('7 号上的 16 枚拆下停用。3 号发动机还能继续飞吗？'), 'clip ticks': count('tick', 64, 86) == 6, 'clip parts': count('part', 64, 86) == 16,
            'q4 parts': count('part', 86, 101) == 16, 'q4 ticks': count('tick', 86, 101) == 2, 'slide 101': any(e['kind'] == 'slide' and e['t'] == 101 and e['dur'] == 2.0 and e['src'] == 'dialog' for e in events),
            'four paths 103': count('path', 103, 103.01) == 4, 'tone 105': any(e['kind'] == 'tone' and e['t'] == 105 and e['gain'] == 0.5 for e in events),
            'swap': count('swap', 112, 115) == 1, 'tone 116.4': any(e['kind'] == 'tone' and abs(e['t'] - 116.4) < 1e-9 and e['gain'] == 0.8 for e in events),
            'same list on ending page': events == events_end}
    ok = not bad and set(kinds) <= allowed and fields_ok and all(need.values()) and span[0] >= 30 and span[1] <= 120
    counts = {k: sum(1 for e in events if e['kind'] == k) for k in kinds}
    record('G6', ok, counts=counts, span=span, required=need, fields_ok=fields_ok, problems=bad[:20],
           note='every frame 64-101: type events vs characters appearing, path events vs links starting to draw, dialog line events vs lines and plan cards appearing')


# ---------------------------------------------------------------- F-checks extended to 64–120
def f2x(browser):
    """F2+: seek-back determinism at moments past 64 (pixels and probe)."""
    pa, pb = new_page(browser, 'f2x-seek'), new_page(browser, 'f2x-direct')
    rows, ok = [], True
    for t, pre in ((70.0, 40.0), (81.0, 97.0), (87.5, 63.5), (93.0, 40.0), (97.3, 70.0), (99.5, 40.0), (102.0, 64.0),
                   (104.0, 119.0), (108.0, 119.0), (112.6, 104.0), (114.0, 119.0), (117.0, 104.0)):
        url = page_for(t)
        load(pa, url + '&play=0'); seek(pa, pre if (pre < HANDOFF) == (t < HANDOFF) else t); seek(pa, t); pa.wait_for_timeout(250)
        a, pra = shot(pa), probe(pa)
        load(pb, f'{url}&t={t}'); b, prb = shot(pb), probe(pb)
        m = diffmax(a, b); n = over(m, 0)
        same = pra == prb
        ok &= n == 0 and same
        rows.append({'t': t, 'via': pre, 'page': url.split('frame=')[1].split('&')[0], 'pixels_differing': n, 'max': m.getextrema()[1], 'probe_equal': same})
    pa.close(); pb.close()
    record('F2+', ok, rows=rows)


COUNT_JS = """() => { const { e7, engine, view } = window.__filmDebug; const E = e7 ?? engine; let drawn = 0;
  for (const [, s] of E.parts) if (s.visible) drawn++; return { drawn, total: E.parts.size }; }"""


def f6x(browser):
    """F6+: every part drawn through question three and four; the ending removes them by plan."""
    page = new_page(browser, 'f6x')
    load(page, FILM + '&play=0')
    rows = {}
    for t in (70.0, 80.0, 90.0, 100.0, 102.0):
        seek(page, t); rows[t] = page.evaluate(COUNT_JS)
    load(page, END + '&play=0')
    for t in (103.0, 105.5, 108.0, 111.5, 113.0):
        seek(page, t); rows[t] = page.evaluate(COUNT_JS)
    page.close()
    # 86.4-96: the 16 stopped blades have faded out and their slots are empty (red outlines); they come back from 96.0.
    ok = all(rows[t]['drawn'] == 2027 for t in (70.0, 80.0, 100.0, 102.0, 103.0, 105.5)) and rows[90.0]['drawn'] == 2011 and rows[111.5]['drawn'] == 1 and rows[113.0]['drawn'] <= 1
    record('F6+', ok, rows={str(k): v for k, v in rows.items()}, note='2,027 parts except while the 16 slots are empty in question four (2,011 at 90 s); the ending takes parts away from 105.6; only blade 001 at 111.5')


FOLD_SPANS = ((86.0, 87.0), (98.6, 99.4))


def f4x(browser):
    """F4+: layout of every text 64–103 each 0.1 s; fold and re-answer frames every 1/60 s (主时间轴一 12.1)."""
    page = new_page(browser, 'f4x')
    load(page, FILM + '&play=0')
    bad, n = [], 0
    for i in range(391):
        t = round(64 + i / 10, 2)
        seek(page, t); n += 1
        for b in page.evaluate(LAYOUT_JS)['bad']:
            # The plan cards' text sits in .plan, not in a step line; the 15-character rule is for answer lines.
            bad.append([t] + b)
    fold_bad, ff = [], 0
    for a, b in FOLD_SPANS:
        for t in frames_of(a, b):
            seek(page, t); ff += 1
            r = page.evaluate(FOLD_JS)
            if r and len(fold_bad) < 20: fold_bad.append([round(t, 3), r[:3]])
    page.close()
    kinds = {}
    for b in bad: kinds.setdefault(' / '.join(map(str, b[1:])), []).append(b[0])
    summary = [[k, v[0], v[-1], len(v)] for k, v in kinds.items()]
    record('F4+', not bad and not fold_bad, samples=n, fold_frames=ff, layout_problems=summary[:30], fold_problems=fold_bad)


def why9x(t):
    if 64.0 <= t < 86.0: return 'clip-q3 (G1: equals frame=clip)'
    if 86.0 <= t <= 87.4: return 'tags out, 3 号 fades, camera push-in, red blades fade'
    if 91.4 <= t <= 91.8: return 'gap tags appear'
    if 96.0 <= t <= 98.5: return 'blades fly in'
    if 98.4 <= t <= 99.0: return 'blade colour back, gap tags out'
    if 98.6 <= t <= 99.4: return 'question two turns green: its old row closes, the turns below move up'
    if 101.0 <= t <= 103.0: return 'back to the split view'
    if 103.0 <= t <= 105.0: return 'fan spins up, airflow'
    if 105.0 <= t <= 111.4: return 'parts go, farthest from blade 001 first'
    if 112.0 <= t <= 115.0: return 'camera back to the opening shot, blade 001 swap'
    if 115.0 <= t <= 117.4: return 'thread and subtitle'
    return 'unplanned'


def f9x(browser):
    """F9+: 86–120: no unplanned single-frame jumps; mean difference every 0.05 s."""
    page = new_page(browser, 'f9x')
    jumps, means = [], []
    for url, a0, a1 in ((FILM, 86.0, 103.0), (END, 103.0, 120.0)):
        load(page, url + '&play=0')
        prev, kept = None, []
        f0, f1 = int(round(a0 * FPS)), int(round(a1 * FPS))
        for f in range(f0, f1 + 1):
            seek(page, f / FPS)
            img = shot(page, (0, 0, 1281, 1080) if url == FILM else (0, 0, 1280, 1080))
            if prev is not None:
                big = sum(diffmax(prev, img).histogram()[61:])
                if big >= 2000: jumps.append([round(f / FPS, 3), big])
            if (f - f0) % 3 == 0:
                if kept:
                    md = mean_diff(kept[-1][1], img)
                    if md > 3: means.append([round(kept[-1][0] / FPS, 3), round(f / FPS, 3), round(md, 2)])
                kept.append((f, img))
            prev = img
    page.close()
    unplanned = [j for j in jumps if why9x(j[0]) == 'unplanned'] + [m for m in means if why9x(m[0]) == 'unplanned']
    record('F9+', not unplanned, single_frame_jumps=[j + [why9x(j[0])] for j in jumps][:40], mean_over_3=[m + [why9x(m[0])] for m in means][:40], unplanned=unplanned,
           note='dialog and model columns (film page) or the 1280 split view (ending page), every frame; 64-86 is covered by G1')


F10X_JS = r"""() => { const out = [];
  // clip-q3's two engine tags, carried over from its 22.0 picture while they fade (86.0-86.2), keep clip-q3's own layout (G1).
  for (const el of document.querySelectorAll('#callout-labels > div')) { if (el.matches('.tag.tone-red, .tag.tone-amber')) continue; const r = el.getBoundingClientRect(); if (r.width && +getComputedStyle(el).opacity > 0.02) out.push([el.innerText.slice(0, 14), r.left, r.top, r.right, r.bottom]); }
  return out; }"""


def f10x(browser):
    """F10+: 86–101 labels and solid parts at least 24 px inside the model column (ghosts do not count, 十一.1)."""
    page = new_page(browser, 'f10x')
    load(page, FILM + '&play=0')
    worst = []
    SOLID = js_of('SOLID_JS')
    for i in range(151):
        t = round(86 + i / 10, 2)
        seek(page, t)
        for name, a, b, c, d in page.evaluate(F10X_JS):
            worst.append((round(min(a - 561, b, 1281 - c, 1080 - d), 1), t, name))
        x0, y0, x1, y1, _ = page.evaluate(SOLID)
        worst.append((round(min(x0 - 561, y0, 1281 - x1, 1080 - y1), 1), t, 'solid parts'))
    page.close()
    w = min(worst)
    record('F10+', w[0] >= 24, worst=w, note='86-101 every 0.1 s, question four labels and every solid part; clip-q3\'s two carried-over tags (clip layout, 23.8 px from the edge) excluded while they fade 86.0-86.2; 101-120 is the split view of the opening, checked by G4 and its own 3B checks')


def f11x(browser):
    """F11+: camera moves past 64 (60 fps; steps and their changes within 4x the median, ends at rest)."""
    page = new_page(browser, 'f11x')
    rows, ok = [], True
    for url, a, b in ((FILM, 86.0, 87.0), (FILM, 101.0, 103.0), (END, 112.0, 113.3), (END, 113.3, 115.0)):
        load(page, url + '&play=0')
        pos = []
        for t in frames_of(a, b):
            seek(page, t); pos.append(probe(page)['camera']['position'])
        v = [math.dist(p, q) for p, q in zip(pos, pos[1:])]
        acc = [abs(y - x) for x, y in zip(v, v[1:])]
        med = sorted(v)[len(v) // 2]; meda = sorted(acc)[len(acc) // 2] or 1e-12
        good = max(v) <= 4 * med and max(acc) <= 4 * meda and v[0] <= 0.2 * med and v[-1] <= 0.2 * med
        ok &= good
        rows.append({'move': [a, b], 'median_step': med, 'max_step_ratio': round(max(v) / med, 2), 'max_change_ratio': round(max(acc) / meda, 2),
                     'start_ratio': round(v[0] / med, 4), 'end_ratio': round(v[-1] / med, 4), 'pass': good})
    page.close()
    record('F11+', ok, moves=rows)


def f15x(browser):
    """F15+: chips and timing labels clear of lines, 64–120 every 0.1 s, fold spans every frame."""
    sys.path.insert(0, HERE)
    page = new_page(browser, 'f15x')
    out, ok = {}, True
    for name, url, times in (('film 64-103', FILM, sorted({round(64 + i / 10, 4) for i in range(391)} | {round(t, 4) for a, b in FOLD_SPANS for t in frames_of(a, b)})),
                             ('ending 103-120', END, [round(103 + i / 10, 2) for i in range(171)])):
        load(page, url + '&play=0')
        hits = {}
        for t in times:
            seek(page, t)
            for h in page.evaluate(F15_JS):
                key = (h['kind'], h['lit'], h['line'], h['text'])
                r = hits.setdefault(key, [t, t, 0]); r[1] = t; r[2] += 1
        rows = [{'kind': k[0], 'lit_line': k[1], 'line': k[2], 'text': k[3], 'from': v[0], 'to': v[1], 'samples': v[2]} for k, v in sorted(hits.items(), key=lambda kv: kv[1][0])]
        fails = [r for r in rows if r['kind'] in ('chip', 'timing')]
        out[name] = {'samples': len(times), 'labels_crossed': fails, 'node_names_under_lit_lines': [r for r in rows if r['kind'] == 'name']}
        ok &= not fails
    page.close()
    record('F15+', ok, **out)


def f14():
    real = [c for c in console if not c['text'].startswith('[vite]')]
    prev = results.get('F14', {})
    record('F14+', not real, messages=real[:20], part_a=prev.get('pass'))


def handoff_sheet(parts):
    """衔接.png: rows at 64 (film vs clip t=0), 103 (film vs ending) and 120 (ending vs opening t=4): reference, film, difference x 10."""
    sheet = Image.new('RGB', (2880, 1620), 'white')
    for row, (ref, film, m) in enumerate(parts):
        y = 540 * row
        sheet.paste(ref.resize((960, 540), Image.LANCZOS), (0, y))
        sheet.paste(film.resize((960, 540), Image.LANCZOS), (960, y))
        sheet.paste(m.point(lambda v: min(255, v * 10)).convert('RGB').resize((960, 540), Image.LANCZOS), (1920, y))
    sheet.save(os.path.join(OUT, '衔接.png'))


CHECKS = [('G1', g1), ('G2', g2), ('G3', g3), ('G5', g5), ('G6', g6), ('F2+', f2x), ('F4+', f4x), ('F6+', f6x), ('F9+', f9x), ('F10+', f10x), ('F11+', f11x), ('F15+', f15x)]
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    if want('G4'):
        a, b, m, c, d, m2 = g4(browser)
        pa = new_page(browser, 'sheet'); load(pa, f'{FILM}&t=64'); f64 = shot(pa); load(pa, f'{NEW}?frame=clip&theme=light&t=0'); c0 = shot(pa); pa.close()
        handoff_sheet([(c0, f64, diffmax(c0, f64)), (d, c, m2), (b, a, m)])
    for key, fn in CHECKS:
        if want(key):
            started = time.time(); fn(browser); print(f'  ({time.time() - started:.0f} s)', flush=True)
    browser.close()
if ONLY is None or 'F14+' in ONLY:
    f14()
