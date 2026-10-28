"""Checks for frame=film-a, main timeline part one (任务说明/主时间轴一任务说明.md, section 九).

Covers 30–64 s: F1–F14 (question one 33–49 s, question two 49–64 s).

Usage: check-film-a.py [--only F1,F3] [--out review/film-a]
Needs the dev server on 5194 (this branch) and the 802c77f baseline on 5195.
Results merge into <out>/results.json, so single checks can be re-run.
"""
import io, json, math, os, sys, time
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

NEW, BASE = 'http://127.0.0.1:5194/frames.html', 'http://127.0.0.1:5195/frames.html'
FILM = f'{NEW}?frame=film-a&theme=light'
FPS = 60
args = sys.argv[1:]
ONLY = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
OUT = args[args.index('--out') + 1] if '--out' in args else os.path.join(os.path.dirname(__file__), '..', 'review', 'film-a')
os.makedirs(OUT, exist_ok=True)
RESULTS_PATH = os.path.join(OUT, 'results.json')
results = json.load(open(RESULTS_PATH)) if os.path.exists(RESULTS_PATH) else {}
console = []

CAM_INIT = """window.__THREE_DEVTOOLS__ = new EventTarget();
window.__THREE_DEVTOOLS__.addEventListener('observe', e => {
  const o = e.detail;
  if (o && typeof o.render === 'function' && o.domElement) {
    const orig = o.render.bind(o);
    o.render = (scene, cam) => { if (cam.isPerspectiveCamera && cam.fov === 24) window.__lastCam = cam; return orig(scene, cam); };
  }
});"""


def record(key, ok, **detail):
    results[key] = {'pass': bool(ok), **detail}
    json.dump(results, open(RESULTS_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f'{key}: {"PASS" if ok else "FAIL"}', json.dumps(detail, ensure_ascii=False)[:600], flush=True)


def want(key):
    return ONLY is None or key in ONLY


def new_page(browser, label):
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.add_init_script(CAM_INIT)
    def on_console(m):
        if m.type == 'error' or (m.type == 'warning'):
            console.append({'page': label, 'type': m.type, 'text': m.text[:300]})
    page.on('console', on_console)
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
    r, g, bl = ImageChops.difference(a, b).split()
    hs = [c.histogram() for c in (r, g, bl)]
    n = a.size[0] * a.size[1] * 3
    return sum(i * v for h in hs for i, v in enumerate(h)) / n


def seek(page, t):
    page.evaluate(f'window.__seek({t})')


def probe(page):
    return page.evaluate('window.__filmProbe()')


# ---------------------------------------------------------------- F1
# Mask of what the new purchase-order -> blade link may change: pixels within
# 5 px of its stroke, plus the counter text box. Measured in the new page.
EDGE_MASK_JS = """() => {
  const svg = document.querySelector('#graph');
  const p = [...svg.querySelectorAll('path')].filter(x => x.getAttribute('d').startsWith('M578 900 C') || x.getAttribute('d').startsWith('M293 410 C'));
  const pts = [];
  for (const q of p) { const L = q.getTotalLength(); for (let i = 0; i <= Math.ceil(L); i++) { const a = q.getPointAtLength(L * i / Math.ceil(L)); pts.push([a.x + 1280, a.y]); } }
  const counter = [...svg.querySelectorAll('text')].find(t => t.textContent.includes('个节点'));
  const r = counter.getBoundingClientRect();
  return { pts, counter: [r.left - 2, r.top - 2, r.right + 2, r.bottom + 2] };
}"""


def edge_mask(page):
    info = page.evaluate(EDGE_MASK_JS)
    mask = Image.new('L', (1920, 1080), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    for x, y in info['pts']:
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=255)
    d.rectangle(info['counter'], fill=255)
    return mask, len(info['pts'])


def f1(browser):
    cases = [('open', ''), ('q3', ''), ('stale', ''), ('net', '')]
    cases += [('clip', f'&t={t}') for t in (0, 6, 12, 18, 21.9)]
    cases += [('opening', f'&t={t}') for t in (3, 8, 12, 15, 17)]
    pa, pb = new_page(browser, 'f1-new'), new_page(browser, 'f1-base')
    rows, ok = [], True
    for frame, extra in cases:
        q = f'?frame={frame}&theme=light{extra}'
        load(pa, NEW + q); load(pb, BASE + q)
        a, b = shot(pa), shot(pb)
        m = diffmax(a, b)
        masked = frame in ('q3', 'stale', 'net', 'clip')
        allowed = 0
        if masked:
            mask, n = edge_mask(pa)
            inside = ImageChops.multiply(m.point(lambda v: 255 if v > 8 else 0), mask)
            allowed = over(inside, 0)
        total = over(m)
        outside = total - allowed
        share = 100 * outside / (1920 * 1080)
        good = share < 0.01
        ok &= good
        rows.append({'frame': frame + extra, 'diff>8': total, 'inside_link_mask': allowed, 'outside_pct': round(share, 5), 'bbox': m.point(lambda v: 255 if v > 8 else 0).getbbox(), 'pass': good})
    pa.close(); pb.close()
    record('F1', ok, rows=rows)
# ---------------------------------------------------------------- F2
def f2(browser):
    pa, pb = new_page(browser, 'f2-seek'), new_page(browser, 'f2-direct')
    load(pa, FILM + '&play=0')
    rows, ok = [], True
    for t in (31.0, 38.6, 44.0, 52.0, 56.0, 61.0):
        seek(pa, 63.5); seek(pa, t)
        pa.wait_for_timeout(250)   # same settle time as load() gives the direct page
        a, pra = shot(pa), probe(pa)
        load(pb, f'{FILM}&t={t}')
        b, prb = shot(pb), probe(pb)
        m = diffmax(a, b)
        n = over(m, 0)
        same = pra == prb
        ok &= n == 0 and same
        where = {k: over(m.crop(box), 0) for k, box in {'dialog': (0, 0, 560, 1080), 'model': (561, 0, 1281, 1080), 'graph': (1281, 0, 1920, 1080)}.items()}
        sample = [(x, y, m.getpixel((x, y))) for y in range(0, 1080) for x in range(1920) if m.getpixel((x, y))][:12] if n else []
        rows.append({'t': t, 'pixels_differing': n, 'by_column': where, 'sample': sample, 'bbox': m.point(lambda v: 255 if v else 0).getbbox(), 'max': m.getextrema()[1], 'probe_equal': same})
    pa.close(); pb.close()
    record('F2', ok, rows=rows)


# ---------------------------------------------------------------- F3
def cam_of(page):
    return page.evaluate("""() => { const c = window.__lastCam; c.updateMatrixWorld();
      const d = new c.position.constructor(0, 0, -1).applyQuaternion(c.quaternion);
      return { p: c.position.toArray(), d: d.toArray() }; }""")


def f3(browser):
    sheet = Image.new('RGB', (2880, 1080), 'white')
    halves, ok = [], True
    for row, (ref, t) in enumerate(((f'{NEW}?frame=net-end&theme=light', 30), (f'{NEW}?frame=clip&theme=light&t=0', 64))):
        pa, pb = new_page(browser, 'f3-ref'), new_page(browser, 'f3-film')
        load(pa, ref); load(pb, f'{FILM}&t={t}')
        a, b = shot(pa), shot(pb)
        m = diffmax(a, b)
        n = over(m)
        ca, cb = cam_of(pa), cam_of(pb)
        dp = math.dist(ca['p'], cb['p'])
        dot = sum(x * y for x, y in zip(ca['d'], cb['d']))
        ang = math.degrees(math.acos(max(-1, min(1, dot))))
        pct = 100 * n / (1920 * 1080)
        good = pct < 0.01 and dp <= 0.002 and ang <= 0.01
        ok &= good
        # 衔接.png: reference, film-a, difference x 10; row 1 is t=30, row 2 is t=64.
        y = 540 * row
        sheet.paste(a.resize((960, 540), Image.LANCZOS), (0, y))
        sheet.paste(b.resize((960, 540), Image.LANCZOS), (960, y))
        sheet.paste(m.point(lambda v: min(255, v * 10)).convert('RGB').resize((960, 540), Image.LANCZOS), (1920, y))
        halves.append({'t': t, 'against': ref.split('?')[1], 'pixels_over8': n, 'pct': round(pct, 5), 'max_channel_diff': m.getextrema()[1],
                       'cam_pos_diff': dp, 'cam_angle_deg': ang, 'pass': good})
        pa.close(); pb.close()
    sheet.save(os.path.join(OUT, '衔接.png'))
    record('F3', ok, halves=halves)


# ---------------------------------------------------------------- F4, F5
EXPECT_Q1 = {
    'meta': '研发 02:07',
    'ask': '第一级涡轮叶片的冷却孔缩小 0.1 毫米，会影响到哪些东西？',
    'steps': ['设计版本 v3.2 → 第一级涡轮叶片', '打孔程序 2 套 · 检验标准 1 份', '在制叶片 300 枚 · 在途铸件 200 件 · 涉及发动机 5 台'],
    'answer': '在制叶片 300 枚 · 在途铸件 200 件 · 涉及发动机 5 台',
    'trace': ['已检索 7 类对象 · 1,284 条关系', '0.6 秒'],
}
LAYOUT_JS = r"""() => {
  const out = { bad: [], lines: [] };
  const vis = el => { let e = el; while (e && e.nodeType === 1) { const s = getComputedStyle(e); if (s.display === 'none' || +s.opacity === 0) return false; e = e.parentElement; } return true; };
  const R = el => el.getBoundingClientRect();
  const col = { dialog: [0, 560], model: [560, 1280], graph: [1280, 1920] };
  const panel = document.querySelector('#dialog').getBoundingClientRect();
  // Dialog: blocks must stay inside the panel and not overlap one another.
  const blocks = [...document.querySelectorAll('#dialog .col-head > span, #dialog .meta, #dialog .ask, #dialog .step, #dialog .answer, #dialog .trace > span')].filter(vis);
  for (const el of blocks) { const r = R(el);
    if (r.left < panel.left - 0.5 || r.right > panel.right + 0.5 || r.top < -0.5 || r.bottom > 1080.5) out.bad.push(['outside dialog', el.className, el.innerText.slice(0, 20)]);
    if (el.scrollWidth > el.clientWidth + 1) out.bad.push(['clipped', el.className, el.innerText.slice(0, 20)]); }
  for (let i = 0; i < blocks.length; i++) for (let j = i + 1; j < blocks.length; j++) {
    const a = blocks[i], b = blocks[j]; if (a.contains(b) || b.contains(a)) continue;
    const p = R(a), q = R(b); const ox = Math.min(p.right, q.right) - Math.max(p.left, q.left), oy = Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top);
    // Two layers of a fold cross-fade on purpose; only compare items in the same layer.
    const la = a.closest('.layer'), lb = b.closest('.layer');
    if (la && lb && la !== lb) continue;
    if (ox > 0.5 && oy > 0.5) out.bad.push(['overlap', a.className, b.className, a.innerText.slice(0, 12), b.innerText.slice(0, 12)]); }
  // Answer lines: at most 15 characters per visual line, digits and punctuation not counted.
  // The folded answer of a past turn is clip-q3's text verbatim (section 四 asks for
  // identical text at 64 s), so it is reported, not failed.
  for (const el of [...document.querySelectorAll('#dialog .past .answer')].filter(vis)) out.lines.push(['past: ' + el.innerText, [...el.innerText.replace(/[\d\s.,·，。？、→…–\-()（）:：a-zA-Z]/g, '')].length]);
  for (const el of [...document.querySelectorAll('#dialog .step .line, #dialog .turn:not(.past) .answer')].filter(vis)) {
    for (const line of el.innerText.split('\n')) { const n = [...line.replace(/[\d\s.,·，。？、→…–\-()（）:：a-zA-Z]/g, '')].length; out.lines.push([line, n]); if (n > 15) out.bad.push(['line too long', line, n]); } }
  // Model column overlays: inside the column, labels not overlapping.
  const ov = [...document.querySelectorAll('#callout-labels > div, .model-caption')].filter(vis);
  // The model column starts where the sliding panel ends (0 before it comes in).
  const mLeft = getComputedStyle(document.querySelector('#dialog')).display === 'none' ? 0 : Math.max(0, panel.right);
  for (const el of ov) { const r = R(el); if (r.left < mLeft || r.right > 1280 || r.top < 0 || r.bottom > 1080) out.bad.push(['outside model', el.className, el.innerText.slice(0, 20)]); }
  for (let i = 0; i < ov.length; i++) for (let j = i + 1; j < ov.length; j++) { const p = R(ov[i]), q = R(ov[j]);
    if (Math.min(p.right, q.right) - Math.max(p.left, q.left) > 0.5 && Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > 0.5) out.bad.push(['overlap model', ov[i].innerText.slice(0, 12), ov[j].innerText.slice(0, 12)]); }
  // Graph: every text inside the column; chips (mono 11.5) not on any other text or node.
  const texts = [...document.querySelectorAll('#graph text')].filter(t => t.textContent.trim() && vis(t) && +(t.getAttribute('opacity') ?? 1) > 0);
  // Nodes only: the r 2.6 dot is the head of a link being drawn, which passes by.
  const circles = [...document.querySelectorAll('#graph circle')].filter(c => vis(c) && +(c.getAttribute('opacity') ?? 1) >= 0.5 && c.getAttribute('r') !== '2.6');
  for (const t of texts) { const r = R(t); if (r.left < 1280 || r.right > 1920) out.bad.push(['outside graph', t.textContent]); }
  for (const c of texts.filter(t => t.getAttribute('font-size') === '11.5')) { const p = R(c);
    for (const t of texts) { if (t === c) continue; const q = R(t);
      if (Math.min(p.right, q.right) - Math.max(p.left, q.left) > 0.5 && Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > 0.5) out.bad.push(['chip on text', c.textContent, t.textContent]); }
    for (const k of circles) { const q = R(k);
      if (Math.min(p.right, q.right) - Math.max(p.left, q.left) > 0.5 && Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > 0.5) out.bad.push(['chip on node', c.textContent]); } }
  return out;
}"""
EXPECT_Q2 = {
    'meta': '总装 02:11',
    'ask': '7 号发动机明早 9 点能按时上试车台吗？',
    'steps': ['核对 9 个模块：8 个到位，1 个缺件', '缺燃烧室组件 1 套，采购单在途，02:40 到厂', '可以按时上试车台 09:00'],
    'answer': '可以按时上试车台 09:00',
    'trace': ['已检索 5 类对象 · 27 条关系', '0.3 秒'],
}
# Every turn as shown: inside a fold cross-fade, the layer that is at least half visible.
DIALOG_JS = r"""() => {
  const T = el => el ? el.innerText.replace(/\s+/g, ' ').trim() : null;
  const turns = [];
  for (const child of document.querySelectorAll('#dialog .turns > *')) {
    const turn = child.classList.contains('swap') ? [...child.querySelectorAll(':scope > .layer')].find(l => +l.style.opacity >= 0.5)?.querySelector('.turn') : child;
    if (!turn) continue;
    turns.push({ meta: T(turn.querySelector('.meta')), ask: T(turn.querySelector('.ask')),
      steps: [...turn.querySelectorAll('.step .line')].map(T), answer: T(turn.querySelector('.answer')),
      past: turn.classList.contains('past'), ems: [...turn.querySelectorAll('.step em')].map(e => e.innerText) });
  }
  return { turns, trace: [...document.querySelectorAll('#dialog .trace span')].map(T) };
}"""
MODULE_TONES_JS = r"""() => { const out = { green: 0, amber: 0, other: 0 };
  for (const c of document.querySelectorAll('#graph g > circle[r="4.5"]')) { const s = c.getAttribute('stroke');
    if (s === 'var(--green)') out.green++; else if (s === 'var(--amber)') out.amber++; else out.other++; }
  return out; }"""


def f4_f5(browser):
    page = new_page(browser, 'f4')
    load(page, FILM + '&play=0')
    bad, text_bad, samples = [], [], 0
    finals = {}
    t = 30.0
    while t <= 64.0001:
        tt = round(t, 3)
        seek(page, tt)
        lay = page.evaluate(LAYOUT_JS)
        for b in lay['bad']:
            if len(bad) < 40: bad.append([round(t, 2)] + b)
        d = page.evaluate(DIALOG_JS)
        turns, trace = d['turns'], d['trace']
        def need(cond, *what):
            if not cond: text_bad.append([round(t, 2)] + list(what))
        if 44.6 <= tt < 47.6:
            q = turns[0]; finals['q1'] = q
            for key in ('meta', 'ask', 'steps'): need(q[key] == EXPECT_Q1[key], 'q1', key, q[key])
            need(trace == EXPECT_Q1['trace'], 'q1 trace', trace)
        if tt >= 48.4:
            q = turns[0]
            need(q['past'] and q['ask'] == EXPECT_Q1['ask'] and q['answer'] == EXPECT_Q1['answer'] and q['meta'] == EXPECT_Q1['meta'], 'q1 past', q)
        if 48.4 <= tt < 49.0: need(trace == EXPECT_Q1['trace'], 'q1 trace held', trace)
        if 58.0 <= tt < 61.0:
            q = turns[1]; finals['q2'] = q
            for key in ('meta', 'ask', 'steps'): need(q[key] == EXPECT_Q2[key], 'q2', key, q[key])
        if 58.0 <= tt < 62.6: need(trace == EXPECT_Q2['trace'], 'q2 trace', trace)
        if tt >= 61.8:
            q = turns[1]
            need(q['past'] and q['ask'] == EXPECT_Q2['ask'] and q['answer'] == EXPECT_Q2['answer'] and q['meta'] == EXPECT_Q2['meta'], 'q2 past', q)
        if tt >= 62.6: need(trace == ['就绪', ''], 'ready', trace)
        samples += 1
        t += 0.1
    lines = []
    for at in (46.0, 49.0, 58.0, 64.0):
        seek(page, at); lines += page.evaluate(LAYOUT_JS)['lines']
    seek(page, 58.0); tones = page.evaluate(MODULE_TONES_JS)
    page.close()
    record('F4', not bad and not text_bad, samples=samples, layout_problems=bad[:20], text_problems=text_bad[:20],
           line_lengths=lines, final_q1=finals.get('q1'), final_q2=finals.get('q2'))
    # F5: numbers read back from the final DOM of each question.
    e1 = [int(x.replace(',', '')) for x in (finals.get('q1') or {}).get('ems', [])]
    ok1 = len(e1) == 5 and e1[2] % 100 == 0 and e1[3] % 100 == 0 and e1[2] // 100 + e1[3] // 100 == e1[4]
    e2 = (finals.get('q2') or {}).get('ems', [])
    n2 = [int(x) for x in e2[:4]] if len(e2) == 5 else []
    ok2 = len(n2) == 4 and n2[0] == n2[1] + n2[2] and n2[3] == n2[2] and tones['green'] == n2[1] and tones['amber'] == n2[2] and e2[4] == '02:40'
    record('F5', ok1 and ok2, q1_read=e1, q2_read=e2, graph_module_tones_58s=tones,
           rule='q1: 在制 / 100 + 在途 / 100 = 发动机台数; q2: 9 = 8 到位 + 1 缺件, the graph shows 8 green and 1 amber modules, 缺 1 套 = 1 缺件')
# ---------------------------------------------------------------- F6
COUNT_JS = """() => { const { e7, view } = window.__filmDebug; let drawn = 0, shown = 0; const faded = [];
  for (const [id, s] of e7.parts) { if (!s.visible) continue; drawn++; if (view.partOpacity(e7, id) > 0.02) shown++; else faded.push(id); }
  return { drawn, shown, faded, total: e7.parts.size }; }"""


def f6(browser):
    page = new_page(browser, 'f6')
    load(page, FILM + '&play=0')
    rows = {}
    for t in (33.0, 45.0, 55.0, 63.0):
        seek(page, t); rows[t] = page.evaluate(COUNT_JS)
    # Section 六.7: no outline lines or depth shells from the opening after 30 s.
    lines = page.evaluate("() => { let n = 0; window.__filmDebug.view.scene.traverse(o => { if (o.isLine || o.isLineSegments || o.type === 'LineSegments2') n++; }); return n; }")
    page.close()
    ok = all(r['drawn'] == 2027 for r in rows.values()) and all(rows[t]['shown'] == 2027 for t in (33.0, 55.0, 63.0)) and lines == 0
    record('F6', ok, rows={str(k): v for k, v in rows.items()}, outline_objects_in_scene=lines,
           note='2,027 = manifest = opening 23 s. At 45 s only the two solid neighbour blades are at opacity 0 (section 十一.3)')


# ---------------------------------------------------------------- F7
# Exploded view (section 六.2, 六.3). Module sections come from partWorldPoints of the live
# engine: 0.02-wide bins along x, per bin the module's min and max radius about the axis.
# Points: every vertex of every part (partWorldPoints) plus points sampled over each triangle at
# `step`, so long cone surfaces with few vertices still fill every bin. Each pair is binned in the
# frame of the module that moves less: two modules moving together keep their sections exactly.
F7_SAMPLE_JS = r"""(step) => { const { e7, THREE } = window.__filmDebug; const y0 = e7.root.position.y, z0 = e7.root.position.z, x0 = e7.root.position.x;
  const mods = {}; const M = new THREE.Matrix4();
  for (const m of e7.modules) { const xs = [], rs = [];
    for (const c of m.components) for (const id of c.parts) { const s = e7.parts.get(id); if (!s) continue;
      if (s.promoted) { s.promoted.updateWorldMatrix(true, false); M.copy(s.promoted.matrixWorld); }
      else { s.group.mesh.updateWorldMatrix(true, false); if (s.index >= 0) M.multiplyMatrices(s.group.mesh.matrixWorld, s.matrix); else M.copy(s.group.mesh.matrixWorld); }
      const e = M.elements, geo = s.group.mesh.geometry, g = geo.getAttribute('position'), ix = geo.index;
      const T = i => { const x = g.getX(i), y = g.getY(i), z = g.getZ(i); return [e[0]*x+e[4]*y+e[8]*z+e[12] - x0, e[1]*x+e[5]*y+e[9]*z+e[13] - y0, e[2]*x+e[6]*y+e[10]*z+e[14] - z0]; };
      const n = ix ? ix.count : g.count;
      for (let t = 0; t < n; t += 3) { const A = T(ix ? ix.getX(t) : t), B = T(ix ? ix.getX(t+1) : t+1), C = T(ix ? ix.getX(t+2) : t+2);
        const L = Math.max(Math.hypot(A[0]-B[0], A[1]-B[1], A[2]-B[2]), Math.hypot(A[0]-C[0], A[1]-C[1], A[2]-C[2]), Math.hypot(B[0]-C[0], B[1]-C[1], B[2]-C[2]));
        const k = Math.max(1, Math.ceil(L / step));
        for (let a = 0; a <= k; a++) for (let b = 0; b <= k - a; b++) { const u = a/k, v = b/k, w = 1-u-v;
          const px = w*A[0]+u*B[0]+v*C[0], py = w*A[1]+u*B[1]+v*C[1], pz = w*A[2]+u*B[2]+v*C[2]; xs.push(px); rs.push(Math.hypot(py, pz)); } } }
    mods[m.meta.id] = { xs: Float32Array.from(xs), rs: Float32Array.from(rs), x: m.group.position.x, y: m.group.position.y, z: m.group.position.z,
      rot: [m.group.rotation.x, m.group.rotation.y, m.group.rotation.z] }; }
  window.__f7 = mods;
  return Object.fromEntries(Object.entries(mods).map(([k, v]) => [k, { n: v.xs.length, x: v.x, y: v.y, z: v.z, rot: v.rot }])); }"""
F7_SECT_JS = r"""([W, X0, NB, frames]) => { const out = {};
  for (const [name, m] of Object.entries(window.__f7)) { out[name] = {};
    for (const f of frames) { const lo = new Array(NB).fill(9), hi = new Array(NB).fill(-9);
      for (let i = 0; i < m.xs.length; i++) { const b = Math.floor((m.xs[i] - f - X0) / W); if (b < 0 || b >= NB) continue; const r = m.rs[i]; if (r < lo[b]) lo[b] = r; if (r > hi[b]) hi[b] = r; }
      out[name][(f + 0).toFixed(6)] = { lo, hi }; } }
  return out; }"""


def f7_sections(page, step, frames):
    info = page.evaluate(F7_SAMPLE_JS, step)
    secs = page.evaluate(F7_SECT_JS, [0.02, -4.0, 400, frames])
    return info, secs


# Combustor pixels on the real picture: drawn as it is, then with every other module hidden,
# then with the combustor hidden; a pixel belongs to the combustor where hiding it changes the frame.
RESTORE_JS = """() => { const { e7, view } = window.__filmDebug; for (const m of e7.modules) m.group.visible = true; view.render(); }"""


def f7(browser, step=0.006):
    page = new_page(browser, 'f7')
    load(page, FILM + '&play=0')
    W, X0, NB = 0.02, -4.0, 400
    ovl = lambda A, B, i: max(0.0, min(A['hi'][i], B['hi'][i]) - max(A['lo'][i], B['lo'][i]))
    seek(page, 49.0)
    _, home = f7_sections(page, step, [0.0])
    mods = list(home)
    H = {m: home[m]['0.000000'] for m in mods}
    base = {(a, b): [ovl(H[a], H[b], i) for i in range(NB)] for k, a in enumerate(mods) for b in mods[k + 1:]}
    worst, moves, samples = {}, [], 0
    for a0, a1 in ((51.6, 53.4), (60.6, 62.4)):
        f = a0
        while f <= a1 + 1e-6:
            seek(page, round(f, 2))
            offs = page.evaluate("() => Object.fromEntries(window.__filmDebug.e7.modules.map(m => [m.meta.id, m.group.position.x]))")
            offs = {k: round(v, 6) + 0.0 for k, v in offs.items()}   # + 0.0 turns -0.0 into 0.0
            frames = sorted(set(offs.values()))
            info, secs = f7_sections(page, step, frames)
            samples += 1
            for name, m in info.items():
                if abs(m['y']) > 1e-9 or abs(m['z']) > 1e-9 or any(abs(r) > 1e-9 for r in m['rot']): moves.append([round(f, 2), name, m['y'], m['z'], m['rot']])
            for (a, b), h in base.items():
                fr = offs[a] if abs(offs[a]) <= abs(offs[b]) else offs[b]   # bins move with the module that moves less
                key = f'{fr:.6f}'
                A, B = secs[a][key], secs[b][key]
                for i in range(NB):
                    e = ovl(A, B, i) - h[i]
                    if e > worst.get((a, b), (-1,))[0]: worst[(a, b)] = (round(e, 5), round(f, 2), round(X0 + i * W, 2))
            f += 0.1
    seek(page, 53.4)
    full_info, full = f7_sections(page, step, [0.0])
    offsets = {k: v['x'] for k, v in full_info.items()}
    F = {m: full[m]['0.000000'] for m in mods}
    # 爆炸图截面.png: min/max radius per module along x, assembled (top) and fully exploded (bottom).
    from PIL import ImageDraw
    colours = {'fan': '#1f77b4', 'fan-cowl': '#17becf', 'compressor': '#2ca02c', 'combustor': '#e2a23a', 'turbine': '#d62728',
               'exhaust': '#9467bd', 'core-casing': '#7f7f7f', 'nacelle': '#8c564b', 'shaft': '#000000'}
    img = Image.new('RGB', (1800, 1000), 'white'); d = ImageDraw.Draw(img)
    for row, (title, sec) in enumerate((('assembled (49.0 s)', H), ('fully exploded (53.4 s)', F))):
        oy = 40 + row * 490
        d.text((40, oy - 30), title + '   x -3.2 .. 2.6 (engine axis, front to the right), radius 0 .. 0.85; per module: min and max radius in 0.02 bins', fill='black')
        X = lambda x: 40 + (x + 3.2) / 5.8 * 1720
        Y = lambda r: oy + 430 - r / 0.85 * 420
        d.rectangle([X(-3.2), Y(0.85), X(2.6), Y(0)], outline='#cccccc')
        for name in mods:
            m, col = sec[name], colours.get(name, '#333333')
            for i in range(NB):
                if m['hi'][i] < -1: continue
                x = X0 + i * W
                d.line([X(x), Y(m['lo'][i]), X(x + W), Y(m['lo'][i])], fill=col, width=2)
                d.line([X(x), Y(m['hi'][i]), X(x + W), Y(m['hi'][i])], fill=col, width=2)
        for k, name in enumerate(colours):
            d.rectangle([40 + k * 190, oy + 445, 52 + k * 190, oy + 457], fill=colours[name]); d.text((58 + k * 190, oy + 445), name, fill='black')
    img.save(os.path.join(OUT, '爆炸图截面.png'))
    # Combustor share on the real 55.0 s picture: pixels the combustor changes in the full frame,
    # against the pixels it covers when it is drawn alone.
    seek(page, 55.0)
    vis = lambda js: (page.evaluate("(f) => { const { e7, view } = window.__filmDebug; for (const m of e7.modules) m.group.visible = new Function('id', f)(m.meta.id); view.render(); }", js), shot(page, COL))[1]
    a = vis("return true"); b = vis("return id !== 'combustor'"); c = vis("return id === 'combustor'"); bg = vis("return false")
    page.evaluate(RESTORE_JS)
    page.close()
    mask = lambda x, y: diffmax(x, y).point(lambda v: 255 if v > 6 else 0)
    shown, solo = over(mask(a, b), 0), over(mask(c, bg), 0)
    share = shown / solo if solo else 0
    top = sorted(((v, k) for k, v in worst.items()), reverse=True)[:3]
    ok = all(v[0] <= 0.003 for v, _ in top) and not moves and share >= 0.7
    record('F7', ok, offsets=offsets, samples=samples, worst3=[{'pair': k, 'excess': v[0], 't': v[1], 'x': v[2]} for v, k in top],
           off_axis_moves=moves[:10], combustor_pixels_shown=shown, combustor_pixels_solo=solo, combustor_share=round(share, 3),
           note=f'excess = overlap of two modules\' radius ranges in a 0.02 bin minus the same in the assembled state (tolerance 0.003), '
                f'bins moving with the module of the pair that moves less; points = vertices + triangle samples every {step}; '
                'every 0.1 s through 51.6-53.4 and 60.6-62.4. Share on the real 55.0 s picture')


# ---------------------------------------------------------------- F8
F8_SETUP = r"""(W) => {
  const { e7, PULLED } = window.__filmDebug;
  const X0 = -1.44, NB = Math.ceil(0.22 / W);
  const dense = (s, matrix, step) => { const geo = s.group.mesh.geometry, g = geo.getAttribute('position'), ix = geo.index, m = matrix.elements, out = [];
    const T = i => { const x = g.getX(i), y = g.getY(i), z = g.getZ(i); return [m[0]*x+m[4]*y+m[8]*z+m[12], m[1]*x+m[5]*y+m[9]*z+m[13], m[2]*x+m[6]*y+m[10]*z+m[14]]; };
    const n = ix ? ix.count : g.count;
    for (let t = 0; t < n; t += 3) { const A = T(ix ? ix.getX(t) : t), B = T(ix ? ix.getX(t+1) : t+1), C = T(ix ? ix.getX(t+2) : t+2);
      const L = Math.max(Math.hypot(A[0]-B[0], A[1]-B[1], A[2]-B[2]), Math.hypot(A[0]-C[0], A[1]-C[1], A[2]-C[2]), Math.hypot(B[0]-C[0], B[1]-C[1], B[2]-C[2]));
      const k = Math.max(1, Math.ceil(L / step));
      for (let i = 0; i <= k; i++) for (let j = 0; j <= k - i; j++) { const u = i/k, v = j/k, w = 1-u-v; out.push(w*A[0]+u*B[0]+v*C[0], w*A[1]+u*B[1]+v*C[1], w*A[2]+u*B[2]+v*C[2]); } }
    return out; };
  const section = (P, sx = 0, sy = 0, sz = 0) => { const lo = new Float32Array(NB).fill(9), hi = new Float32Array(NB).fill(-9);
    for (let i = 0; i < P.length; i += 3) { const b = Math.floor((P[i] + sx - X0) / W); if (b < 0 || b >= NB) continue; const r = Math.hypot(P[i+1] + sy, P[i+2] + sz); if (r < lo[b]) lo[b] = r; if (r > hi[b]) hi[b] = r; }
    return { lo, hi }; };
  const bs = e7.parts.get(PULLED);
  const bladePts = dense(bs, bs.matrix, 0.0012);
  const cands = [];
  for (const [id, s] of e7.parts) { if (id === PULLED) continue; const m = s.meta;
    if (m.axial[1] < -1.42 || m.axial[0] > -1.24 || m.radius[1] < 0.24 || m.radius[0] > 0.53) continue;
    cands.push({ id, comp: m.component, sec: section(dense(s, s.matrix, 0.0015)) }); }
  const rest = section(bladePts);
  const c = e7.getPart(PULLED).center, rl = Math.hypot(c[1], c[2]);
  window.__f8 = { W, NB, X0, section, bladePts, cands, rest, ry: c[1] / rl, rz: c[2] / rl };
  return cands.length;
}"""
F8_STEP = r"""() => {
  const { e7, view } = window.__filmDebug; const F = window.__f8; const pr = window.__filmProbe();
  const ax = pr.pulled.axial, rad = pr.pulled.radial;
  const now = F.section(F.bladePts, ax, F.ry * rad, F.rz * rad);
  const ov = (a, b, i) => Math.max(0, Math.min(a.hi[i], b.hi[i]) - Math.max(a.lo[i], b.lo[i]));
  const bad = []; let worst = 0;
  const ghostOf = window.__filmDebug.ghostOf; let ghosts = 0;
  for (const c of F.cands) { const op = view.partOpacity(e7, c.id); if (op <= 0.02) continue;
    // Section 十一.3: only solid parts must give way; a part with any ghosting is see-through.
    if (ghostOf(c.id) > 0.001) { ghosts++; continue; }
    // Assembled position (ax = rad = 0) is the opening's own state: only overlap beyond it counts.
    const home = ax === 0 && rad === 0;
    const exempt = home || c.comp === 'turbine.stage-1-blades' || (c.comp === 'turbine.stage-1-disk' && rad === 0);
    for (let i = 0; i < F.NB; i++) { const o = ov(now, c.sec, i) - (exempt ? ov(F.rest, c.sec, i) : 0);
      if (o > worst) worst = o;
      if (o > 0.003) bad.push([c.id, +(F.X0 + i * F.W).toFixed(3), +o.toFixed(4), +op.toFixed(3)]); } }
  return { ax, rad, worst, ghosts, bad: bad.slice(0, 6) };
}"""
FADED_JS = """() => { const { e7, view } = window.__filmDebug; return [...e7.parts.keys()].filter(id => e7.parts.get(id).visible && view.partOpacity(e7, id) <= 0.02); }"""


def f8(browser):
    page = new_page(browser, 'f8')
    load(page, FILM + '&play=0')
    out = {}
    for W in (0.02, 0.005):
        seek(page, 30.0)
        n = page.evaluate(F8_SETUP, W)
        bad, worst, frames = [], 0, 0
        f = int(36.9 * FPS)
        while f <= int(48.2 * FPS):
            seek(page, f / FPS)
            r = page.evaluate(F8_STEP)
            worst = max(worst, r['worst'] if r['rad'] or r['ax'] else 0)
            if r['bad'] and len(bad) < 10: bad.append([round(f / FPS, 3), r['ax'], r['rad'], r['bad']])
            frames += 1
            f += 1 if W == 0.02 else 4
        out[str(W)] = {'candidates': n, 'frames': frames, 'violations': bad}
    seek(page, 42.0)
    faded = page.evaluate(FADED_JS)
    pulled = probe(page)['pulled']['id']
    page.close()
    ok = all(not v['violations'] for v in out.values())
    record('F8', ok, pulled=pulled, faded_while_out=faded, bins=out,
           note='section 十一.3: only solid parts (ghost amount 0) with opacity > 0.02 are checked; ghosted parts may be passed through. '
                'Overlap already present with the blade in its assembled place is not counted; the disk slot overlap only while the blade slides along the slot (no radial offset)')


# ---------------------------------------------------------------- F9
COL = (561, 0, 1281, 1080)


def f9(browser):
    page = new_page(browser, 'f9')
    load(page, FILM + '&play=0')
    frames, f0, f1 = [], int(34 * FPS), int(48 * FPS)
    jumps, means = [], []
    prev = None
    for f in range(f0, f1 + 1):
        seek(page, f / FPS)
        img = shot(page, COL)
        if prev is not None:
            m = diffmax(prev, img)
            big = sum(m.histogram()[61:])
            if big >= 2000: jumps.append([round(f / FPS, 3), big])
        if (f - f0) % 3 == 0:
            frames.append((f, img))
        prev = img
    for (fa, a), (fb, b) in zip(frames, frames[1:]):
        md = mean_diff(a, b)
        if md > 3: means.append([round(fa / FPS, 3), round(fb / FPS, 3), round(md, 2)])
    page.close()
    def why(t):
        if 38.0 <= t <= 38.6: return 'close-up window opens (wipe)'
        if 46.6 <= t <= 47.1: return 'close-up window closes'
        if 38.4 <= t <= 40.0: return 'window blade turns and opens its cutaway'
        if 40.8 <= t <= 41.6: return 'film-hole rows light up'
        if 44.0 <= t <= 44.8: return 'number tags appear'
        if 36.2 <= t <= 37.2: return 'engine turns to ghost'
        if 37.0 <= t <= 38.2 or 46.6 <= t <= 48.6: return 'camera move'
        if 47.4 <= t <= 48.4: return 'ghost goes away'
        return 'unplanned'
    unplanned = [j for j in jumps if why(j[0]) == 'unplanned'] + [m for m in means if why(m[0]) == 'unplanned']
    record('F9', not unplanned, window='34.0-48.0 s (52-61 s belongs to question two)',
           single_frame_jumps=[j + [why(j[0])] for j in jumps], mean_over_3=[m + [why(m[0])] for m in means], unplanned=unplanned)


# ---------------------------------------------------------------- F10
F10_JS = r"""() => {
  const panel = document.querySelector('#dialog');
  const left = getComputedStyle(panel).display === 'none' ? 0 : Math.max(0, panel.getBoundingClientRect().right);
  const rects = [];
  for (const el of document.querySelectorAll('#callout-labels > div')) { if (+el.style.opacity === 0) continue; const r = el.getBoundingClientRect(); rects.push(['label', el.innerText.slice(0, 14), r.left, r.top, r.right, r.bottom]); }
  for (const el of document.querySelectorAll('#callouts rect')) { const r = el.getBoundingClientRect(); rects.push(['window', '', r.left, r.top, r.right, r.bottom]); }
  return { left, right: 1280, rects };
}"""
SOLID_JS = r"""() => { const { e7, colCam, view, ghostOf } = window.__filmDebug; const T = window.__filmDebug.THREE;
  // Solid parts as drawn: visible, opacity > 0.02 and not ghosted (section 十一.1: ghosts do not count).
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, ghosts = 0; const v = new T.Vector3();
  for (const [id, s] of e7.parts) { if (!s.visible || view.partOpacity(e7, id) <= 0.02) continue; if (ghostOf(id) > 0.001) { ghosts++; continue; }
    const P = e7.partWorldPoints(id); if (!P) continue;
    for (let i = 0; i < P.length; i += 3) { v.set(P[i], P[i+1], P[i+2]).project(colCam); const x = 561 + (v.x * 0.5 + 0.5) * 720, y = (-v.y * 0.5 + 0.5) * 1080;
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } }
  return [x0, y0, x1, y1, ghosts]; }"""


def f10(browser, t0=30.0, t1=64.0):
    page = new_page(browser, 'f10')
    load(page, FILM + '&play=0')
    page.add_style_tag(content='#callouts, #callout-labels, .model-caption { visibility: hidden !important; }')
    bg = (0xee, 0xf0, 0xee)
    worst_pix, worst_solid, worst_over, ghost_times = [], [], [], []
    t = t0
    while t <= t1 + 1e-4:
        seek(page, round(t, 2))
        info = page.evaluate(F10_JS)
        left, right = info['left'], info['right']
        x0, y0, x1, y1, ghosts = page.evaluate(SOLID_JS) if t >= 33.0 else (0, 0, 0, 0, 1)
        if t >= 33.0:
            worst_solid.append((round(min(x0 - 560, y0, 1280 - x1, 1080 - y1), 1), round(t, 2)))
        for kind, name, a, b, c, d in info['rects']:
            worst_over.append((round(min(a - left, b, right - c, 1080 - d), 1), round(t, 2), kind, name))
        # On the real picture: every non-background canvas pixel outside the close-up window.
        # It decides wherever nothing is ghosted, and 30-33 s (column width changes, F10 counts the net's shell there).
        if t < 33.0 or not ghosts:
            img = shot(page)
            col = img.crop((int(math.ceil(left)) + 1, 0, right, 1080))
            diff = ImageChops.difference(col, Image.new('RGB', col.size, bg))
            r, g, b = diff.split(); m = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > 3 else 0)
            from PIL import ImageDraw
            for kind, _, a, b2, c, d in info['rects']:
                if kind == 'window': ImageDraw.Draw(m).rectangle([a - left - 3, b2 - 3, c - left + 3, d + 3], fill=0)
            box = m.getbbox()
            if box: worst_pix.append((min(box[0] + 1, box[1], col.size[0] - box[2], 1080 - box[3]), round(t, 2)))
        else:
            ghost_times.append(round(t, 2))
        t += 0.1
    page.close()
    wp, ws, wo = min(worst_pix), min(worst_solid), min(worst_over) if worst_over else (999,)
    ok = wp[0] >= 24 and ws[0] >= 24 and wo[0] >= 24
    record('F10', ok, worst_picture_px=wp, worst_solid_parts_px=ws, worst_overlay_px=wo,
           ghosted_span=[ghost_times[0], ghost_times[-1], len(ghost_times)] if ghost_times else [],
           note='section 十一.1: ghosts do not count. picture = non-background pixels of the real frame, used at 30-33 s and wherever '
                'no part is ghosted; solid_parts = every visible, unghosted part projected (33 s on); overlay = labels and close-up window')


# ---------------------------------------------------------------- F11
def f11(browser):
    page = new_page(browser, 'f11')
    load(page, FILM + '&play=0')
    rows, ok = [], True
    for a, b in ((30.3, 32.4), (37.0, 38.2), (46.6, 48.6)):
        pos = []
        for f in range(int(round(a * FPS)), int(round(b * FPS)) + 1):
            seek(page, f / FPS); pos.append(probe(page)['camera']['position'])
        v = [math.dist(p, q) for p, q in zip(pos, pos[1:])]
        acc = [abs(y - x) for x, y in zip(v, v[1:])]
        med = sorted(v)[len(v) // 2]; meda = sorted(acc)[len(acc) // 2]
        good = max(v) <= 4 * med and max(acc) <= 4 * meda and v[0] <= 0.2 * med and v[-1] <= 0.2 * med
        ok &= good
        rows.append({'move': [a, b], 'median_step': med, 'max_step_ratio': round(max(v) / med, 2),
                     'max_change_ratio': round(max(acc) / meda, 2), 'start_ratio': round(v[0] / med, 4), 'end_ratio': round(v[-1] / med, 4), 'pass': good})
    # The pulled blade's own path: velocity through the axial -> radial corner.
    blade = []
    for f in range(int(37.0 * FPS), int(38.2 * FPS) + 1):
        seek(page, f / FPS); p = probe(page)['pulled']; blade.append((p['axial'], p['radial']))
    vb = [math.dist(p, q) for p, q in zip(blade, blade[1:])]
    jump = max(abs(y - x) for x, y in zip(vb, vb[1:])) / (sorted(vb)[len(vb) // 2] or 1)
    page.close()
    record('F11', ok, moves=rows, blade_speed_change_max_over_median=round(jump, 3), note='51.6-53.4 and 60.0-62.6 belong to question two')
# ---------------------------------------------------------------- F12, F13
HOPS = [('design', 'blade', 36.2, 36.8), ('blade', 'drill', 40.2, 40.6), ('blade', 'std', 40.3, 40.7),
        ('blade', 'mwo', 42.8, 43.3), ('blade', 'po', 43.0, 43.6)]
FRAME_JS = r"""() => { const p = window.__filmProbe();
  const ask = document.querySelector('#dialog .turn:not(.past) .ask');
  return { drawing: p.graph.drawing.map(d => d[0] + '>' + d[1]), lit: p.graph.litEdges.map(e => e[0] + '>' + e[1]),
    ask: ask ? [...ask.textContent].length : 0, steps: document.querySelectorAll('#dialog .step').length,
    ems: [...document.querySelectorAll('#dialog .step em')].map(e => e.textContent).join('|'),
    ax: p.pulled.axial, rad: p.pulled.radial, _t: p.t }; }"""


def f12_f13(browser):
    page = new_page(browser, 'f12')
    load(page, FILM + '&play=0')
    events = page.evaluate('window.__events')
    timeline = []
    for f in range(int(32.9 * FPS), int(49.0 * FPS) + 1):
        seek(page, f / FPS); timeline.append((f, page.evaluate(FRAME_JS)))
    page.close()
    first = lambda pred: next((f for f, s in timeline if pred(s)), None)
    # F12: each query link starts drawing / is finished within one frame of the table.
    rows, ok = [], True
    for a, b, ta, tb in HOPS:
        key = f'{a}>{b}'
        s = first(lambda s: key in s['drawing'] or key in s['lit'])
        e = first(lambda s: key in s['lit'])
        ds, de = (s - ta * FPS) if s is not None else 99, (e - tb * FPS) if e is not None else 99
        good = abs(ds) <= 1 and abs(de) <= 1
        ok &= good
        rows.append({'link': key, 'start_frame_err': round(ds, 2), 'end_frame_err': round(de, 2), 'pass': good})
    record('F12', ok, links=rows, note='timing half only; the 64 s DOM comparison belongs to question two')
    # F13: sound events against what the picture does.
    bad, n = [], {}
    type_frames = [f for (f, s), (_, p) in zip(timeline[1:], timeline) if s['ask'] > p['ask']]
    types = [e['t'] for e in events if e['kind'] == 'type']
    if len(types) != len(type_frames): bad.append(['type count', len(types), len(type_frames)])
    for et, f in zip(types, type_frames):
        if abs(f - et * FPS) > 1: bad.append(['type', et, f / FPS])
    step_frames = [f for (f, s), (_, p) in zip(timeline[1:], timeline) if s['steps'] > p['steps']]
    lines = [e['t'] for e in events if e['kind'] == 'line' and 36.0 < e['t'] < 44.0]
    for et, f in zip(lines, step_frames):
        if abs(f - et * FPS) > 1: bad.append(['line', et, f / FPS])
    paths = [e['t'] for e in events if e['kind'] == 'path']
    for (a, b, ta, tb), et in zip(HOPS, paths):
        if abs(et - ta) * FPS > 1: bad.append(['path', et, ta])
    finals = [('2', 40.8, 0.3, 0), ('1', 40.9, 0.3, 1), ('300', 43.9, 0.35, 2), ('200', 44.05, 0.35, 3), ('5', 44.2, 0.3, 4)]
    ticks = sorted(e['t'] for e in events if e['kind'] == 'tick')
    for (val, at, dur, i), et in zip(finals, ticks):
        # The frame from which the number stays on its final value (flicker may touch it earlier).
        win = [(f, s) for f, s in timeline if at <= s['_t'] <= at + 1.5]
        off = [f for f, s in win if not (len(s['ems'].split('|')) > i and s['ems'].split('|')[i] == val)]
        f = (off[-1] + 1) if off else (win[0][0] if win else None)
        if f is None or abs(f - et * FPS) > 1: bad.append(['tick', val, et, f and f / FPS])
    parts = [e['t'] for e in events if e['kind'] == 'part']
    moved = first(lambda s: s['ax'] > 0)
    radial = first(lambda s: s['rad'] > 0)
    back = next((f for f, s in timeline if f > 46 * FPS and s['rad'] < 0.063), None)
    home = next((f for f, s in timeline if f > 46 * FPS and s['ax'] == 0 and s['rad'] == 0), None)
    for et, f in zip(parts, [moved, radial, back, home]):
        if f is None or abs(f - et * FPS) > 1.5: bad.append(['part', et, f and f / FPS])
    for e in events: n[e['kind']] = n.get(e['kind'], 0) + 1
    record('F13', not bad, counts=n, problems=bad[:20], note='a value or motion that starts at an event time shows up on the first frame at or after it')


# ---------------------------------------------------------------- F14
def f14():
    real = [c for c in console if not c['text'].startswith('[vite]')]
    record('F14', not real, messages=real[:20])


# ---------------------------------------------------------------- run
CHECKS = [('F1', f1), ('F2', f2), ('F3', f3), ('F4', f4_f5), ('F6', f6), ('F7', f7), ('F8', f8), ('F9', f9), ('F10', f10), ('F11', f11), ('F12', f12_f13)]
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
    for key, fn in CHECKS:
        if want(key) or (key == 'F4' and want('F5')) or (key == 'F12' and want('F13')):
            started = time.time(); fn(browser); print(f'  ({time.time() - started:.0f} s)', flush=True)
    browser.close()
if ONLY is None or 'F14' in ONLY:
    f14()
